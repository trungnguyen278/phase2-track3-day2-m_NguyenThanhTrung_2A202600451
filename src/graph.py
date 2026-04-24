"""LangGraph Multi-Memory Agent.

State: MemoryState
Nodes:
  extract → retrieve_memory → build_prompt → call_llm → write_back
Router logic gom 4 memory backends, inject vào prompt theo section.
"""
from __future__ import annotations

from typing import Any, TypedDict

import tiktoken
from langgraph.graph import StateGraph, END
from openai import OpenAI

from .config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_EMBED_MODEL,
    REDIS_URL,
    PROFILE_PATH,
    EPISODIC_PATH,
    CHROMA_PATH,
    SEMANTIC_COLLECTION,
    EPISODIC_COLLECTION,
    SHORT_TERM_MAX_TURNS,
    MEMORY_TOKEN_BUDGET,
)
from .extractor import Extractor
from .memory import (
    ShortTermMemory,
    ProfileMemory,
    EpisodicMemory,
    SemanticMemory,
)


class MemoryState(TypedDict, total=False):
    user_message: str
    messages: list[dict]
    user_profile: dict
    episodes: list[dict]
    semantic_hits: list[dict]
    extracted: dict
    prompt: list[dict]
    assistant_response: str
    memory_budget: int
    token_usage: dict


try:
    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    _ENC = None


def _count_tokens(text: str) -> int:
    if _ENC is None:
        return max(1, len(text) // 4)
    return len(_ENC.encode(text))


DEFAULT_ORDER = ["PROFILE", "EPISODIC", "SEMANTIC", "RECENT"]


def _priority_order(intent: str, has_semantic_query: bool) -> list[str]:
    """Trả thứ tự ưu tiên section dựa trên intent của lượt hiện tại."""
    intent = (intent or "").lower()
    if intent == "question" or has_semantic_query:
        return ["SEMANTIC", "PROFILE", "EPISODIC", "RECENT"]
    if intent == "experience":
        return ["EPISODIC", "PROFILE", "SEMANTIC", "RECENT"]
    if intent in ("preference", "fact"):
        return ["PROFILE", "EPISODIC", "SEMANTIC", "RECENT"]
    return DEFAULT_ORDER


def _trim_to_budget(sections: list[tuple[str, str]], budget: int) -> list[tuple[str, str]]:
    """Trim các section theo thứ tự ưu tiên do caller truyền vào.

    sections là list[(section_name, content)] theo thứ tự ưu tiên giảm dần.
    Cắt content khi vượt ngân sách token.
    """
    kept: list[tuple[str, str]] = []
    used = 0
    for name, content in sections:
        t = _count_tokens(content)
        if used + t <= budget:
            kept.append((name, content))
            used += t
            continue
        remaining = budget - used
        if remaining <= 32:
            break
        if _ENC is not None:
            tokens = _ENC.encode(content)[:remaining]
            truncated = _ENC.decode(tokens) + "\n…[trimmed]"
        else:
            truncated = content[: remaining * 4] + "\n…[trimmed]"
        kept.append((name, truncated))
        used += remaining
        break
    return kept


class MultiMemoryAgent:
    def __init__(
        self,
        use_memory: bool = True,
        api_key: str = OPENAI_API_KEY,
        model: str = OPENAI_MODEL,
        memory_budget: int = MEMORY_TOKEN_BUDGET,
    ):
        self.use_memory = use_memory
        self.model = model
        self.memory_budget = memory_budget
        self._client = (
            OpenAI(api_key=api_key)
            if api_key and not api_key.startswith("sk-REPLACE")
            else None
        )

        self.short_term = ShortTermMemory(max_turns=SHORT_TERM_MAX_TURNS)
        self.profile = ProfileMemory(PROFILE_PATH, redis_url=REDIS_URL)
        self.episodic = EpisodicMemory(
            EPISODIC_PATH,
            vector_persist_path=CHROMA_PATH,
            collection_name=EPISODIC_COLLECTION,
            api_key=api_key,
            embed_model=OPENAI_EMBED_MODEL,
        )
        self.semantic = SemanticMemory(
            persist_path=CHROMA_PATH,
            collection_name=SEMANTIC_COLLECTION,
            api_key=api_key,
            embed_model=OPENAI_EMBED_MODEL,
        )
        self.extractor = Extractor(api_key=api_key, model=model)

        self._graph = self._build_graph()
        self._last_token_usage: dict = {}

    # ---------- nodes ----------
    def _node_extract(self, state: MemoryState) -> MemoryState:
        extracted = self.extractor.extract(state["user_message"])
        return {"extracted": extracted}

    def _node_retrieve(self, state: MemoryState) -> MemoryState:
        if not self.use_memory:
            return {
                "user_profile": {},
                "episodes": [],
                "semantic_hits": [],
                "messages": [],
            }
        extracted = state.get("extracted", {})
        query = state["user_message"]

        profile_facts = self.profile.all_facts()

        ep_obj = extracted.get("episodic") or {}
        ep_query = (
            extracted.get("query_for_semantic")
            or (ep_obj.get("topic") if isinstance(ep_obj, dict) else None)
            or query
        )
        episodes = self.episodic.search(ep_query, k=3)

        sem_query = extracted.get("query_for_semantic") or query
        sem_hits = self.semantic.search(sem_query, k=3)

        recent = self.short_term.get_messages()
        return {
            "user_profile": profile_facts,
            "episodes": episodes,
            "semantic_hits": sem_hits,
            "messages": recent,
        }

    def _node_build_prompt(self, state: MemoryState) -> MemoryState:
        system_parts = [
            "Bạn là trợ lý tiếng Việt có memory dài hạn. Dùng thông tin trong <MEMORY> để trả lời cá nhân hóa, ngắn gọn, đúng trọng tâm."
        ]

        if self.use_memory:
            profile = state.get("user_profile") or {}
            episodes = state.get("episodes") or []
            sem_hits = state.get("semantic_hits") or []
            recent = state.get("messages") or []

            profile_block = (
                "\n".join(f"- {k}: {v}" for k, v in profile.items()) if profile else "(no profile)"
            )
            episodic_block = (
                "\n".join(
                    f"- [{ep['timestamp'][:10]}] {ep['topic']}: {ep['summary']} → {ep['outcome']}"
                    for ep in episodes
                )
                if episodes
                else "(no relevant episodes)"
            )
            semantic_block = (
                "\n".join(f"- {h['text']}" for h in sem_hits) if sem_hits else "(no semantic hits)"
            )
            recent_block = (
                "\n".join(f"{m['role']}: {m['content']}" for m in recent)
                if recent
                else "(no recent turns)"
            )

            block_map = {
                "PROFILE": profile_block,
                "EPISODIC": episodic_block,
                "SEMANTIC": semantic_block,
                "RECENT": recent_block,
            }
            extracted = state.get("extracted") or {}
            order = _priority_order(
                intent=extracted.get("intent", ""),
                has_semantic_query=bool(extracted.get("query_for_semantic")),
            )
            sections = [(name, block_map[name]) for name in order]
            trimmed = _trim_to_budget(sections, self.memory_budget)
            mem_block = "\n".join(f"### {name}\n{content}" for name, content in trimmed)
            system_parts.append(f"<MEMORY>\n{mem_block}\n</MEMORY>")
        else:
            system_parts.append("(Memory disabled — chỉ dùng lượt hiện tại.)")

        prompt: list[dict] = [{"role": "system", "content": "\n\n".join(system_parts)}]
        if self.use_memory:
            for m in state.get("messages") or []:
                if m["role"] in ("user", "assistant"):
                    prompt.append(m)
        prompt.append({"role": "user", "content": state["user_message"]})
        return {"prompt": prompt}

    def _node_call_llm(self, state: MemoryState) -> MemoryState:
        prompt = state["prompt"]
        if self._client is None:
            # Offline stub for tests without API key.
            tail = prompt[-1]["content"]
            return {
                "assistant_response": f"[offline-stub] Đã nhận: {tail[:80]}",
                "token_usage": {"prompt": sum(_count_tokens(m['content']) for m in prompt), "completion": 0},
            }
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=prompt,
            temperature=0.3,
        )
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        token_usage = {
            "prompt": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion": getattr(usage, "completion_tokens", 0) if usage else 0,
        }
        return {"assistant_response": text, "token_usage": token_usage}

    def _node_write_back(self, state: MemoryState) -> MemoryState:
        user_msg = state["user_message"]
        assistant = state["assistant_response"]
        self.short_term.add("user", user_msg)
        self.short_term.add("assistant", assistant)

        if not self.use_memory:
            return {}

        extracted = state.get("extracted") or {}
        updates = extracted.get("profile_updates") or {}
        deletes = [k for k in (extracted.get("profile_deletes") or []) if k not in updates]
        for key in deletes:
            self.profile.delete_fact(key)
        for key, value in updates.items():
            self.profile.set_fact(key, value, source="extracted")
        ep = extracted.get("episodic")
        if ep and isinstance(ep, dict) and ep.get("topic"):
            self.episodic.log(
                topic=ep.get("topic", ""),
                summary=ep.get("summary", ""),
                outcome=ep.get("outcome", ""),
                tags=ep.get("tags") or [],
            )
        return {}

    # ---------- graph ----------
    def _build_graph(self):
        g = StateGraph(MemoryState)
        g.add_node("extract", self._node_extract)
        g.add_node("retrieve", self._node_retrieve)
        g.add_node("build_prompt", self._node_build_prompt)
        g.add_node("call_llm", self._node_call_llm)
        g.add_node("write_back", self._node_write_back)

        g.set_entry_point("extract")
        g.add_edge("extract", "retrieve")
        g.add_edge("retrieve", "build_prompt")
        g.add_edge("build_prompt", "call_llm")
        g.add_edge("call_llm", "write_back")
        g.add_edge("write_back", END)
        return g.compile()

    # ---------- public API ----------
    def chat(self, user_message: str) -> dict[str, Any]:
        state: MemoryState = {
            "user_message": user_message,
            "memory_budget": self.memory_budget,
        }
        out = self._graph.invoke(state)
        self._last_token_usage = out.get("token_usage", {})
        return {
            "response": out["assistant_response"],
            "extracted": out.get("extracted", {}),
            "profile": out.get("user_profile", {}),
            "episodes": out.get("episodes", []),
            "semantic_hits": out.get("semantic_hits", []),
            "token_usage": out.get("token_usage", {}),
            "prompt": out.get("prompt", []),
        }

    def reset_memory(self) -> None:
        self.short_term.clear()
        self.profile.clear()
        self.episodic.clear()
        self.semantic.clear()

"""Episodic memory: append-only JSON log + optional vector index.

JSON là source of truth (audit + deletion by id); vector index (Chroma +
OpenAI embeddings) chỉ phục vụ retrieval. Fallback keyword search qua
JSON log khi không có API key.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from ._vector_index import VectorIndex


class EpisodicMemory:
    def __init__(
        self,
        path: str | Path,
        vector_persist_path: str | None = None,
        collection_name: str = "episodic_kb",
        api_key: str = "",
        embed_model: str = "text-embedding-3-small",
    ):
        self.path = Path(path)
        self._episodes: list[dict[str, Any]] = []
        self._load()

        self._vector: VectorIndex | None = None
        if vector_persist_path:
            self._vector = VectorIndex(
                persist_path=vector_persist_path,
                collection_name=collection_name,
                api_key=api_key,
                embed_model=embed_model,
            )

    @property
    def use_vector(self) -> bool:
        return self._vector is not None and self._vector.use_vector

    # ---------- JSON store ----------
    def _load(self) -> None:
        if self.path.exists():
            try:
                self._episodes = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._episodes = []
        else:
            self._episodes = []

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._episodes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---------- public API ----------
    def log(
        self,
        topic: str,
        summary: str,
        outcome: str,
        tags: list[str] | None = None,
    ) -> str:
        ts = datetime.now(timezone.utc).isoformat()
        ep_id = f"ep_{ts}_{len(self._episodes)}"
        ep = {
            "id": ep_id,
            "timestamp": ts,
            "topic": topic,
            "summary": summary,
            "outcome": outcome,
            "tags": tags or [],
        }
        self._episodes.append(ep)
        self._flush()
        if self._vector is not None:
            text = f"{topic}: {summary} → {outcome}"
            self._vector.upsert(
                ep_id,
                text,
                {"topic": topic, "tags": ",".join(tags or []), "ts": ts},
            )
        return ep_id

    def search(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        if self._vector is not None:
            hits = self._vector.query(query, k)
            by_id = {ep["id"]: ep for ep in self._episodes if "id" in ep}
            out: list[dict[str, Any]] = []
            for h in hits:
                ep = by_id.get(h["id"])
                if ep:
                    out.append(ep)
            if out:
                return out
            # vector miss (empty collection or no hit) → keyword fallback
        return self._keyword_search(query, k)

    def _keyword_search(self, query: str, k: int) -> list[dict[str, Any]]:
        q = query.lower()
        scored: list[tuple[int, dict]] = []
        for ep in self._episodes:
            hay = " ".join(
                [ep.get("topic", ""), ep.get("summary", ""), " ".join(ep.get("tags", []))]
            ).lower()
            score = sum(1 for tok in q.split() if tok and tok in hay)
            if score:
                scored.append((score, ep))
        scored.sort(key=lambda x: (-x[0], x[1]["timestamp"]), reverse=False)
        return [ep for _, ep in scored[:k]]

    def all_episodes(self) -> list[dict[str, Any]]:
        return list(self._episodes)

    def render(self, episodes: list[dict] | None = None) -> str:
        eps = episodes if episodes is not None else self._episodes
        if not eps:
            return "(no episodes)"
        return "\n".join(
            f"- [{ep['timestamp'][:10]}] {ep['topic']}: {ep['summary']} → {ep['outcome']}"
            for ep in eps
        )

    def delete(self, ep_id: str) -> bool:
        before = len(self._episodes)
        self._episodes = [e for e in self._episodes if e.get("id") != ep_id]
        if len(self._episodes) == before:
            return False
        self._flush()
        if self._vector is not None:
            self._vector.delete([ep_id])
        return True

    def clear(self) -> None:
        self._episodes = []
        self._flush()
        if self._vector is not None:
            self._vector.clear()

"""LLM-based extractor: phân loại intent + rút profile facts + episodic outcome.

Dùng JSON mode của OpenAI để parse ổn định. Có fallback rule-based nếu
LLM trả về lỗi.
"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL


_EXTRACT_SYSTEM = """Bạn là memory extractor cho một AI agent.
Cho 1 lượt user message, trả về JSON object với các field:
- intent: một trong ["preference", "fact", "experience", "question", "chitchat"]
- profile_updates: dict {key: value} các fact về user (vd: {"name": "Linh", "allergy": "đậu nành"}). Dùng key tiếng Việt không dấu, snake_case.
- profile_deletes: list[str] các key cần xóa (khi user muốn quên)
- episodic: null hoặc object {"topic": str, "summary": str, "outcome": str, "tags": [str]}
- query_for_semantic: string nếu user đang hỏi về kiến thức/FAQ, else null

CHÚ Ý conflict: nếu user sửa một fact cũ (vd: "À nhầm, tôi dị ứng đậu nành"),
hãy set profile_updates[allergy] = "đậu nành" để ghi đè.
Luôn trả JSON hợp lệ, không có text thừa."""


class Extractor:
    def __init__(self, api_key: str = OPENAI_API_KEY, model: str = OPENAI_MODEL):
        self.model = model
        self._client = OpenAI(api_key=api_key) if api_key and not api_key.startswith("sk-REPLACE") else None

    def extract(self, user_message: str) -> dict[str, Any]:
        if self._client is None:
            return self._rule_based(user_message)
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _EXTRACT_SYSTEM},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            raw = resp.choices[0].message.content or "{}"
            return self._normalize(json.loads(raw))
        except Exception:
            return self._rule_based(user_message)

    def _normalize(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": d.get("intent", "chitchat"),
            "profile_updates": d.get("profile_updates") or {},
            "profile_deletes": d.get("profile_deletes") or [],
            "episodic": d.get("episodic"),
            "query_for_semantic": d.get("query_for_semantic"),
        }

    def _rule_based(self, msg: str) -> dict[str, Any]:
        low = msg.lower()
        updates: dict[str, Any] = {}
        m = re.search(r"t[êe]n\s+(?:t[ôo]i|m[ìi]nh)\s+l[àa]\s+([\w\s]+?)(?:[.,!?]|$)", low)
        if m:
            updates["name"] = m.group(1).strip().title()
        if "dị ứng" in low or "di ung" in low:
            m2 = re.search(r"d[ịi]\s*[ứu]ng\s+([\w\s]+?)(?:[.,!?]|$)", low)
            if m2:
                updates["allergy"] = m2.group(1).strip()
        intent = "preference" if updates else ("question" if "?" in msg else "chitchat")
        return {
            "intent": intent,
            "profile_updates": updates,
            "profile_deletes": [],
            "episodic": None,
            "query_for_semantic": msg if intent == "question" else None,
        }

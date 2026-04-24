"""Semantic knowledge base (FAQ, tài liệu) trên Chroma."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ._vector_index import VectorIndex


class SemanticMemory:
    def __init__(
        self,
        persist_path: str | Path,
        collection_name: str = "semantic_kb",
        api_key: str = "",
        embed_model: str = "text-embedding-3-small",
    ):
        self._index = VectorIndex(
            persist_path=str(persist_path),
            collection_name=collection_name,
            api_key=api_key,
            embed_model=embed_model,
        )

    @property
    def use_vector(self) -> bool:
        return self._index.use_vector

    def add(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        self._index.upsert(doc_id, text, metadata)

    def add_many(self, docs: list[dict[str, Any]]) -> None:
        self._index.upsert_many(docs)

    def search(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        return self._index.query(query, k)

    def render(self, hits: list[dict[str, Any]]) -> str:
        if not hits:
            return "(no semantic hits)"
        return "\n".join(f"- {h['text']}" for h in hits)

    def count(self) -> int:
        return self._index.count()

    def clear(self) -> None:
        self._index.clear()

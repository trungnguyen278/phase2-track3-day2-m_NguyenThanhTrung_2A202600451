"""Chroma-backed vector index, reusable cho semantic KB và episodic search.

Khi có OpenAI API key → OpenAI embeddings (text-embedding-3-small).
Không có key → dummy embedder + keyword fallback (cho demo offline).
"""
from __future__ import annotations

from typing import Any

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction


class _DummyEmbedding(EmbeddingFunction[Documents]):
    def __call__(self, input: Documents) -> Embeddings:  # type: ignore[override]
        return [[0.0] * 8 for _ in input]

    def name(self) -> str:  # pragma: no cover
        return "dummy"


def _is_real_key(api_key: str) -> bool:
    return bool(api_key) and not api_key.startswith("sk-REPLACE")


class VectorIndex:
    """Thin wrapper quanh Chroma collection.

    Cung cấp upsert(id, text, metadata), query(text, k), delete(ids), clear(), count().
    `use_vector=False` → chỉ lưu doc text, search bằng keyword overlap.
    """

    def __init__(
        self,
        persist_path: str,
        collection_name: str,
        api_key: str = "",
        embed_model: str = "text-embedding-3-small",
    ):
        self.persist_path = persist_path
        self.collection_name = collection_name
        self.use_vector = _is_real_key(api_key)

        self._client = chromadb.PersistentClient(path=persist_path)
        if self.use_vector:
            self._embed_fn = OpenAIEmbeddingFunction(
                api_key=api_key, model_name=embed_model
            )
        else:
            self._embed_fn = _DummyEmbedding()

        self._collection = self._client.get_or_create_collection(
            name=collection_name, embedding_function=self._embed_fn
        )

    def upsert(
        self, doc_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> None:
        self._collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata or {"source": "manual"}],
        )

    def upsert_many(self, docs: list[dict[str, Any]]) -> None:
        ids = [d["id"] for d in docs]
        texts = [d["text"] for d in docs]
        metas = [d.get("metadata", {"source": "manual"}) for d in docs]
        self._collection.upsert(ids=ids, documents=texts, metadatas=metas)

    def query(self, text: str, k: int = 3) -> list[dict[str, Any]]:
        if self.use_vector:
            res = self._collection.query(query_texts=[text], n_results=k)
            docs = res.get("documents", [[]])[0]
            ids = res.get("ids", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[None] * len(docs)])[0]
            return [
                {"id": i, "text": d, "metadata": m, "distance": dist}
                for i, d, m, dist in zip(ids, docs, metas, dists)
            ]
        return self._keyword_fallback(text, k)

    def _keyword_fallback(self, query: str, k: int) -> list[dict[str, Any]]:
        got = self._collection.get()
        ids = got.get("ids", [])
        docs = got.get("documents", [])
        metas = got.get("metadatas", [])
        q_tokens = [t for t in query.lower().split() if t]
        scored: list[tuple[int, dict]] = []
        for i, d, m in zip(ids, docs, metas):
            score = sum(1 for tok in q_tokens if tok in d.lower())
            if score:
                scored.append(
                    (score, {"id": i, "text": d, "metadata": m, "distance": None})
                )
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:k]]

    def delete(self, ids: list[str]) -> None:
        if ids:
            self._collection.delete(ids=ids)

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name, embedding_function=self._embed_fn
        )

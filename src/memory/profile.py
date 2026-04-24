"""Long-term user profile store.

Backend lựa chọn tự động:
  - Redis (khi REDIS_URL hợp lệ và server responsive)
  - JSON file (fallback offline)

Cùng một API: set_fact / get_fact / delete_fact / all_facts / clear.
Fact mới ghi đè fact cũ cho cùng key (conflict → newest wins).
`updated_at` được lưu để audit/TTL về sau.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProfileMemory:
    NAMESPACE = "profile:"

    def __init__(self, path: str | Path, redis_url: str = ""):
        self.path = Path(path)
        self._redis = None
        self._backend = "json"
        self._store: dict[str, dict[str, Any]] = {}

        if redis_url:
            try:
                import redis as _redis

                client = _redis.from_url(
                    redis_url, decode_responses=True, socket_timeout=2
                )
                client.ping()
                self._redis = client
                self._backend = "redis"
            except Exception:
                self._redis = None
                self._backend = "json"

        if self._backend == "json":
            self._load()

    @property
    def backend(self) -> str:
        return self._backend

    # ---------- JSON helpers ----------
    def _load(self) -> None:
        if self.path.exists():
            try:
                self._store = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._store = {}
        else:
            self._store = {}

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---------- public API ----------
    def set_fact(self, key: str, value: Any, source: str = "user") -> None:
        entry = {"value": value, "source": source, "updated_at": _iso_now()}
        if self._redis is not None:
            self._redis.set(self.NAMESPACE + key, json.dumps(entry, ensure_ascii=False))
            return
        self._store[key] = entry
        self._flush()

    def get_fact(self, key: str) -> Any | None:
        if self._redis is not None:
            raw = self._redis.get(self.NAMESPACE + key)
            if not raw:
                return None
            try:
                return json.loads(raw).get("value")
            except json.JSONDecodeError:
                return None
        entry = self._store.get(key)
        return entry["value"] if entry else None

    def delete_fact(self, key: str) -> bool:
        if self._redis is not None:
            return bool(self._redis.delete(self.NAMESPACE + key))
        if key in self._store:
            del self._store[key]
            self._flush()
            return True
        return False

    def all_facts(self) -> dict[str, Any]:
        if self._redis is not None:
            out: dict[str, Any] = {}
            for k in self._redis.keys(self.NAMESPACE + "*"):
                raw = self._redis.get(k)
                if not raw:
                    continue
                try:
                    out[k[len(self.NAMESPACE):]] = json.loads(raw)["value"]
                except Exception:
                    continue
            return out
        return {k: v["value"] for k, v in self._store.items()}

    def render(self) -> str:
        facts = self.all_facts()
        if not facts:
            return "(no profile facts)"
        return "\n".join(f"- {k}: {v}" for k, v in facts.items())

    def clear(self) -> None:
        if self._redis is not None:
            keys = self._redis.keys(self.NAMESPACE + "*")
            if keys:
                self._redis.delete(*keys)
            return
        self._store = {}
        self._flush()

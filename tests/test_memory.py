"""Smoke tests cho 4 memory backends + improvements (Redis, vector episodic, adaptive trim)."""
import os
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.memory import ShortTermMemory, ProfileMemory, EpisodicMemory, SemanticMemory
from src.graph import _priority_order, DEFAULT_ORDER


def test_short_term():
    m = ShortTermMemory(max_turns=3)
    for i in range(5):
        m.add("user", f"q{i}")
        m.add("assistant", f"a{i}")
    msgs = m.get_messages()
    assert len(msgs) == 6, f"expected 6, got {len(msgs)}"
    assert msgs[0]["content"] == "q2", "sliding window should drop oldest"
    print("[OK] short_term sliding window")


def test_profile_conflict_json():
    p = Path("data/_test_profile.json")
    if p.exists():
        p.unlink()
    prof = ProfileMemory(p)
    assert prof.backend == "json"
    prof.set_fact("allergy", "sữa bò")
    assert prof.get_fact("allergy") == "sữa bò"
    prof.set_fact("allergy", "đậu nành")
    assert prof.get_fact("allergy") == "đậu nành", "newest fact must win"
    prof.set_fact("name", "Linh")
    assert prof.all_facts() == {"allergy": "đậu nành", "name": "Linh"}
    assert prof.delete_fact("name") is True
    assert prof.delete_fact("nonexistent") is False
    p.unlink()
    print("[OK] profile JSON backend (conflict + delete)")


def test_profile_redis_optional():
    url = os.getenv("REDIS_URL", "")
    if not url:
        print("[skip] profile Redis (REDIS_URL not set)")
        return
    prof = ProfileMemory(Path("data/_unused.json"), redis_url=url)
    if prof.backend != "redis":
        print("[skip] profile Redis (connection failed, fell back to JSON)")
        return
    prof.clear()
    prof.set_fact("allergy", "sữa bò")
    prof.set_fact("allergy", "đậu nành")
    assert prof.get_fact("allergy") == "đậu nành"
    assert prof.all_facts() == {"allergy": "đậu nành"}
    prof.clear()
    assert prof.all_facts() == {}
    print("[OK] profile Redis backend")


def test_episodic_keyword():
    p = Path("data/_test_episodic.json")
    if p.exists():
        p.unlink()
    ep = EpisodicMemory(p)  # no vector
    ep.log("debug docker", "container không connect postgres", "dùng service name", ["docker", "postgres"])
    ep.log("học Python", "confuse async/await", "giải thích event loop", ["python", "async"])
    hits = ep.search("docker postgres")
    assert len(hits) >= 1
    assert "docker" in hits[0]["topic"].lower() or "docker" in " ".join(hits[0]["tags"]).lower()
    p.unlink()
    print("[OK] episodic keyword search (no vector)")


def test_episodic_vector():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-REPLACE"):
        print("[skip] episodic vector (no OPENAI_API_KEY)")
        return
    p = Path("data/_test_episodic_vec.json")
    vec_path = Path("data/_test_chroma_vec")
    if p.exists():
        p.unlink()
    if vec_path.exists():
        shutil.rmtree(vec_path, ignore_errors=True)

    ep = EpisodicMemory(
        p, vector_persist_path=str(vec_path), collection_name="ep_test", api_key=api_key
    )
    assert ep.use_vector
    ep.log(
        "bug backend",
        "service A không gọi được service B trong docker compose",
        "dùng tên service trong docker-compose.yml thay vì localhost",
        ["docker", "network"],
    )
    ep.log(
        "Python async",
        "quên await coroutine → thread bị block",
        "phải await mọi IO call",
        ["python", "async"],
    )
    # Query bằng từ KHÁC keyword — vector phải match semantic
    hits = ep.search("hai container không kết nối được với nhau", k=1)
    assert hits, "vector search should return hit for semantic query"
    assert "docker" in hits[0]["topic"].lower() or "docker" in hits[0]["tags"][0].lower()
    ep.clear()
    p.unlink()
    shutil.rmtree(vec_path, ignore_errors=True)
    print("[OK] episodic vector search (semantic match beyond keywords)")


def test_semantic():
    path = Path("data/_test_chroma")
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    sem = SemanticMemory(persist_path=path, collection_name="test_kb", api_key="")
    sem.add("1", "LangGraph dùng StateGraph TypedDict qua node.")
    sem.add("2", "Redis là in-memory key-value store cho profile.")
    hits = sem.search("Redis key value")
    assert any("Redis" in h["text"] for h in hits), f"got: {hits}"
    shutil.rmtree(path, ignore_errors=True)
    print("[OK] semantic keyword fallback")


def test_priority_order():
    assert _priority_order("question", False)[0] == "SEMANTIC"
    assert _priority_order("chitchat", True)[0] == "SEMANTIC"
    assert _priority_order("experience", False)[0] == "EPISODIC"
    assert _priority_order("preference", False)[0] == "PROFILE"
    assert _priority_order("fact", False)[0] == "PROFILE"
    assert _priority_order("chitchat", False) == DEFAULT_ORDER
    # RECENT luôn đứng cuối (ưu tiên thấp nhất)
    for intent in ["question", "experience", "preference", "chitchat"]:
        assert _priority_order(intent, False)[-1] == "RECENT", intent
    print("[OK] adaptive priority order")


if __name__ == "__main__":
    test_short_term()
    test_profile_conflict_json()
    test_profile_redis_optional()
    test_episodic_keyword()
    test_episodic_vector()
    test_semantic()
    test_priority_order()
    print("\nAll backend smoke tests passed.")

"""End-to-end smoke test cho MultiMemoryAgent."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.graph import MultiMemoryAgent


def seed_semantic(agent: MultiMemoryAgent):
    agent.semantic.add_many([
        {"id": "doc1", "text": "LangGraph dùng StateGraph để quản lý state TypedDict qua các node và edge."},
        {"id": "doc2", "text": "Redis là in-memory key-value store, thường dùng làm long-term profile cho agent."},
        {"id": "doc3", "text": "Chroma là vector DB persistent, hỗ trợ OpenAI embeddings qua embedding_function."},
        {"id": "doc4", "text": "Async/await trong Python chạy trên event loop, blocking IO phải được await."},
    ])


def run():
    agent = MultiMemoryAgent(use_memory=True)
    agent.reset_memory()
    seed_semantic(agent)

    turns = [
        "Xin chào, tên mình là Linh.",
        "Mình thích Python, không thích Java.",
        "Tôi dị ứng sữa bò.",
        "À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò.",
        "Tên tôi là gì?",
        "LangGraph là gì?",
    ]

    for i, msg in enumerate(turns, 1):
        print(f"\n--- Turn {i} ---")
        print(f"USER: {msg}")
        out = agent.chat(msg)
        print(f"ASSISTANT: {out['response']}")
        print(f"  intent={out['extracted'].get('intent')}  updates={out['extracted'].get('profile_updates')}  tokens={out['token_usage']}")

    print("\n--- Final profile ---")
    print(agent.profile.render())
    allergy = agent.profile.get_fact("allergy")
    assert allergy and "đậu nành" in allergy.lower(), f"expected allergy='đậu nành', got {allergy!r}"
    print("\n[OK] conflict update: allergy =", allergy)


if __name__ == "__main__":
    run()

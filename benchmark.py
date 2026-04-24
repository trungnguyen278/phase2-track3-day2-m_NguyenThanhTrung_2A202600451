"""Benchmark 10 multi-turn conversations: no-memory vs with-memory.

Mỗi scenario:
  - Seed (optional): các lượt chuẩn bị state (profile/episodic) — chỉ áp dụng cho with-memory.
  - Probe turns: các lượt kiểm tra agent có nhớ/retrieve đúng không.
  - Pass criteria: substring hoặc regex trên câu trả lời probe cuối.

Output: BENCHMARK.md với bảng kết quả + tổng hợp token usage.

Coverage:
  1-3 profile recall, 4 conflict update, 5-6 episodic recall,
  7-8 semantic retrieval, 9 trim/token budget, 10 combine profile+semantic.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.graph import MultiMemoryAgent


SEMANTIC_DOCS = [
    {"id": "kb_langgraph", "text": "LangGraph dùng StateGraph để quản lý state TypedDict, mỗi node nhận state và trả dict để merge vào state."},
    {"id": "kb_redis", "text": "Redis là in-memory key-value store, phù hợp làm long-term profile vì tốc độ truy xuất dưới 1ms."},
    {"id": "kb_chroma", "text": "Chroma là vector DB persistent, hỗ trợ OpenAIEmbeddingFunction qua api_key và model_name."},
    {"id": "kb_async", "text": "Async/await trong Python chạy trên event loop; IO blocking phải được await để không chặn thread."},
    {"id": "kb_docker", "text": "Khi hai container muốn kết nối nhau trong Docker Compose, dùng service name thay vì localhost."},
]


SCENARIOS: list[dict] = [
    {
        "id": 1,
        "name": "Profile recall: tên user sau 4 lượt",
        "category": "profile",
        "seed": [
            "Xin chào, tên mình là Linh.",
            "Mình đang học Python.",
            "Hôm nay trời đẹp.",
            "Mình thích cà phê.",
        ],
        "probe": "Tên tôi là gì?",
        "pass_regex": r"linh",
    },
    {
        "id": 2,
        "name": "Profile recall: ngôn ngữ yêu thích",
        "category": "profile",
        "seed": [
            "Mình thích Python, không thích Java.",
            "Mình đang dùng FastAPI cho backend.",
        ],
        "probe": "Bạn đề xuất ngôn ngữ nào cho mình viết script tự động hoá?",
        "pass_regex": r"python",
    },
    {
        "id": 3,
        "name": "Profile recall: nghề nghiệp",
        "category": "profile",
        "seed": [
            "Mình là data scientist tại VinUni.",
            "Hôm nay mình gặp bug ở pipeline.",
        ],
        "probe": "Tóm tắt giúp mình biết mình làm nghề gì.",
        "pass_regex": r"data\s*scientist|data_scientist|khoa học dữ liệu",
    },
    {
        "id": 4,
        "name": "Conflict update: dị ứng sữa bò → đậu nành",
        "category": "conflict",
        "seed": [
            "Tôi dị ứng sữa bò.",
            "Hôm nay tôi ăn phở.",
            "À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò.",
        ],
        "probe": "Mình dị ứng cái gì?",
        "pass_regex": r"đậu\s*nành",
        "fail_regex": r"sữa\s*bò",
    },
    {
        "id": 5,
        "name": "Episodic recall: bug Docker/Postgres",
        "category": "episodic",
        "seed_episodes": [
            {
                "topic": "debug docker postgres",
                "summary": "container backend không connect được postgres vì dùng localhost",
                "outcome": "đổi sang service name 'db' trong docker-compose, connect OK",
                "tags": ["docker", "postgres", "network"],
            }
        ],
        "probe": "Lần trước mình debug docker với postgres, giải pháp là gì?",
        "pass_regex": r"service\s*name|tên\s*service|\bdb\b",
    },
    {
        "id": 6,
        "name": "Episodic recall: nhầm async/await",
        "category": "episodic",
        "seed_episodes": [
            {
                "topic": "học async python",
                "summary": "user confuse vì gọi hàm async mà không await, IO block thread",
                "outcome": "giải thích event loop, phải await mọi coroutine",
                "tags": ["python", "async", "event_loop"],
            }
        ],
        "probe": "Mình hay quên gì khi viết async Python?",
        "pass_regex": r"await|event\s*loop",
    },
    {
        "id": 7,
        "name": "Semantic retrieval: LangGraph là gì",
        "category": "semantic",
        "seed": [],
        "probe": "LangGraph quản lý state kiểu gì?",
        "pass_regex": r"stategraph|typeddict|node",
    },
    {
        "id": 8,
        "name": "Semantic retrieval: Docker Compose networking",
        "category": "semantic",
        "seed": [],
        "probe": "Hai container docker nối với nhau thế nào?",
        "pass_regex": r"service\s*name|tên\s*service",
    },
    {
        "id": 9,
        "name": "Trim/token budget: 12 lượt chit-chat rồi recall",
        "category": "trim",
        "seed": [
            "Mình tên Khánh.",
            "Hôm nay trời nắng.",
            "Mình vừa uống cà phê.",
            "Đang nghe nhạc lofi.",
            "Mình có 2 con mèo.",
            "Đọc sách sci-fi cuối tuần.",
            "Mình ghét dậy sớm.",
            "Tập gym 3 buổi một tuần.",
            "Thích pizza nấm.",
            "Đang học tiếng Nhật.",
            "Mê phim Studio Ghibli.",
            "Mới mua laptop mới.",
        ],
        "probe": "Tên mình là gì?",
        "pass_regex": r"khánh|khanh",
    },
    {
        "id": 10,
        "name": "Combine profile + semantic",
        "category": "combine",
        "seed": [
            "Tên mình là Minh, mình là backend dev thích Redis.",
        ],
        "probe": "Giới thiệu ngắn về Redis cho mình (nhớ gọi tên mình nhé).",
        "pass_regex": r"minh.*redis|redis.*minh|minh[^a-z]*(in-memory|key.?value)",
    },
]


def _seed_memory(agent: MultiMemoryAgent, sc: dict) -> None:
    for ep in sc.get("seed_episodes", []):
        agent.episodic.log(
            topic=ep["topic"],
            summary=ep["summary"],
            outcome=ep["outcome"],
            tags=ep.get("tags", []),
        )
    for msg in sc.get("seed", []):
        agent.chat(msg)


def _seed_nomem(agent: MultiMemoryAgent, sc: dict) -> None:
    # No-memory: vẫn phát các seed turn để công bằng (agent sẽ thấy trong short-term
    # của chính nó, nhưng trong no-memory mode short-term không được inject vào prompt
    # qua node retrieve). Ở đây ta reset luôn để tương đương "cold agent".
    # Tuy nhiên để mô phỏng sát — ta vẫn chạy seed để lịch sử user/assistant có thật.
    for msg in sc.get("seed", []):
        agent.chat(msg)


def _check(response: str, sc: dict) -> tuple[bool, str]:
    low = response.lower()
    ok = bool(re.search(sc["pass_regex"], low))
    fail_r = sc.get("fail_regex")
    if fail_r and re.search(fail_r, low):
        return False, "matched fail_regex"
    return ok, ("pass_regex match" if ok else "no pass_regex match")


def run_scenario(sc: dict) -> dict:
    # --- with-memory ---
    mem_agent = MultiMemoryAgent(use_memory=True)
    mem_agent.reset_memory()
    mem_agent.semantic.add_many(SEMANTIC_DOCS)
    _seed_memory(mem_agent, sc)
    out_mem = mem_agent.chat(sc["probe"])
    mem_ok, mem_reason = _check(out_mem["response"], sc)

    # --- no-memory ---
    nomem_agent = MultiMemoryAgent(use_memory=False)
    nomem_agent.reset_memory()
    # nomem: không seed semantic, không lưu profile/episodic trong retrieve
    _seed_nomem(nomem_agent, sc)
    out_nomem = nomem_agent.chat(sc["probe"])
    nomem_ok, _ = _check(out_nomem["response"], sc)

    return {
        "id": sc["id"],
        "name": sc["name"],
        "category": sc["category"],
        "probe": sc["probe"],
        "no_memory_response": out_nomem["response"],
        "no_memory_pass": nomem_ok,
        "no_memory_tokens": out_nomem["token_usage"],
        "with_memory_response": out_mem["response"],
        "with_memory_pass": mem_ok,
        "with_memory_tokens": out_mem["token_usage"],
        "delta_tokens": (
            out_mem["token_usage"].get("prompt", 0)
            - out_nomem["token_usage"].get("prompt", 0)
        ),
        "reason": mem_reason,
    }


def _trunc(s: str, n: int = 140) -> str:
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def render_markdown(results: list[dict]) -> str:
    lines = ["# Benchmark: No-memory vs With-memory", ""]
    lines.append(
        "> **Họ tên:** Nguyễn Thành Trung · **MSSV:** 2A202600451 · **Lab #17 — VinUni AICB**"
    )
    lines.append("")
    lines.append("**Model:** gpt-4o-mini | **Scenarios:** 10 multi-turn conversations")
    lines.append("")
    lines.append("## Kết quả tổng quan")
    lines.append("")
    lines.append("| # | Category | Scenario | No-mem | With-mem | Δ prompt tokens |")
    lines.append("|---|----------|----------|:------:|:--------:|----------------:|")
    for r in results:
        lines.append(
            f"| {r['id']} | {r['category']} | {r['name']} | "
            f"{'✅' if r['no_memory_pass'] else '❌'} | "
            f"{'✅' if r['with_memory_pass'] else '❌'} | "
            f"{r['delta_tokens']:+d} |"
        )

    pass_no = sum(1 for r in results if r["no_memory_pass"])
    pass_mem = sum(1 for r in results if r["with_memory_pass"])
    tot_no = sum(r["no_memory_tokens"].get("prompt", 0) for r in results)
    tot_mem = sum(r["with_memory_tokens"].get("prompt", 0) for r in results)
    lines += [
        "",
        f"- No-memory pass rate: **{pass_no}/10**",
        f"- With-memory pass rate: **{pass_mem}/10**",
        f"- Tổng prompt tokens: no-mem **{tot_no}**, with-mem **{tot_mem}** "
        f"(+{tot_mem - tot_no} cho memory injection)",
        "",
        "## Chi tiết từng scenario",
        "",
    ]
    for r in results:
        lines += [
            f"### {r['id']}. {r['name']}  _[{r['category']}]_",
            f"- **Probe:** {r['probe']}",
            f"- **No-memory** ({'PASS' if r['no_memory_pass'] else 'FAIL'}, "
            f"tokens={r['no_memory_tokens']}): _{_trunc(r['no_memory_response'])}_",
            f"- **With-memory** ({'PASS' if r['with_memory_pass'] else 'FAIL'}, "
            f"tokens={r['with_memory_tokens']}): _{_trunc(r['with_memory_response'])}_",
            "",
        ]
    return "\n".join(lines)


def main():
    results = []
    for sc in SCENARIOS:
        print(f"[{sc['id']}/10] {sc['name']} ...")
        try:
            r = run_scenario(sc)
            results.append(r)
            print(
                f"    no-mem={'PASS' if r['no_memory_pass'] else 'FAIL'}  "
                f"with-mem={'PASS' if r['with_memory_pass'] else 'FAIL'}  "
                f"Δtokens={r['delta_tokens']:+d}"
            )
        except Exception as e:
            print(f"    ERROR: {e}")
            results.append(
                {
                    "id": sc["id"],
                    "name": sc["name"],
                    "category": sc["category"],
                    "probe": sc["probe"],
                    "no_memory_response": f"ERROR: {e}",
                    "no_memory_pass": False,
                    "no_memory_tokens": {"prompt": 0, "completion": 0},
                    "with_memory_response": f"ERROR: {e}",
                    "with_memory_pass": False,
                    "with_memory_tokens": {"prompt": 0, "completion": 0},
                    "delta_tokens": 0,
                    "reason": "exception",
                }
            )

    md = render_markdown(results)
    out_path = ROOT / "BENCHMARK.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()

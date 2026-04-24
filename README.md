# Lab #17 — Multi-Memory Agent với LangGraph

> **Họ tên:** Nguyễn Thành Trung
> **MSSV:** 2A202600451
> **Khóa học:** VinUni AICB — Phase 2 · Track 3 · Day 02
> **Email:** trung2782002@gmail.com

Agent quản lý 4 tầng memory, orchestrate bằng LangGraph, benchmark so sánh với/không có memory trên 10 hội thoại đa lượt.

## Cấu trúc repo

```
├── src/
│   ├── memory/
│   │   ├── short_term.py     # sliding-window buffer
│   │   ├── profile.py        # Redis (nếu REDIS_URL) hoặc JSON KV; conflict handling (newest wins)
│   │   ├── episodic.py       # JSON log + optional vector index (Chroma)
│   │   ├── semantic.py       # Chroma + OpenAI embeddings
│   │   └── _vector_index.py  # shared Chroma wrapper (fallback keyword khi không có API key)
│   ├── extractor.py          # LLM-based extractor (intent + updates + episodic)
│   ├── graph.py              # MultiMemoryAgent + LangGraph StateGraph + adaptive trim
│   └── config.py
├── tests/
│   ├── test_memory.py        # unit test cho 4 backends
│   └── test_graph.py         # end-to-end 6 turns
├── benchmark.py              # 10 multi-turn scenarios, no-mem vs with-mem
├── BENCHMARK.md              # bảng kết quả + chi tiết
├── REFLECTION.md             # PII, limitations, takeaways
├── requirements.txt
├── .env.example
└── .gitignore
```

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -r requirements.txt

cp .env.example .env
# điền OPENAI_API_KEY vào .env
```

## Chạy

```bash
# unit test 4 backends
python tests/test_memory.py

# end-to-end 6 turns (conflict update test)
python tests/test_graph.py

# benchmark 10 scenarios → BENCHMARK.md
python benchmark.py
```

## Graph flow

```
extract → retrieve → build_prompt → call_llm → write_back → END
```

- `extract`: LLM JSON mode rút `intent`, `profile_updates`, `profile_deletes`, `episodic`, `query_for_semantic`.
- `retrieve`: gom profile (all facts) + episodic (top-3 vector / keyword fallback) + semantic (top-3 vector) + short-term (N lượt gần nhất).
- `build_prompt`: inject theo 4 section, **adaptive priority theo intent**:
  - `question` / có `query_for_semantic` → `SEMANTIC > PROFILE > EPISODIC > RECENT`
  - `experience` → `EPISODIC > PROFILE > SEMANTIC > RECENT`
  - `preference` / `fact` → `PROFILE > EPISODIC > SEMANTIC > RECENT`
  - Trim bằng `tiktoken` theo `MEMORY_TOKEN_BUDGET`.
- `call_llm`: OpenAI chat completion, trả về response + token usage.
- `write_back`: apply deletes trước rồi updates (conflict → newest wins), ghi short-term, ghi episodic nếu có outcome (cả JSON log và vector index).

## Backend matrix

| Memory | Primary | Fallback | Config |
|--------|---------|----------|--------|
| Short-term | deque sliding window | — | `SHORT_TERM_MAX_TURNS` |
| Profile | Redis (khi `REDIS_URL` set & up) | JSON file | `REDIS_URL`, `PROFILE_PATH` |
| Episodic | JSON log + Chroma vector (khi có API key) | JSON + keyword search | `EPISODIC_PATH`, `CHROMA_PATH` |
| Semantic | Chroma vector + OpenAI embeddings | Chroma + keyword on stored text | `CHROMA_PATH`, `OPENAI_EMBED_MODEL` |

## Kết quả benchmark

| | No-memory | With-memory |
|---|:---:|:---:|
| Pass rate | **2/10** | **10/10** |
| Prompt tokens (tổng) | 675 | 3738 |

Xem `BENCHMARK.md` cho chi tiết từng scenario.

## Reflection

Xem `REFLECTION.md` — thảo luận PII, privacy-by-design, limitations kỹ thuật, và các điểm sẽ fail khi scale.

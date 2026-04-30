# Week8 Smoke Eval Report

Week 8：从“搜得到”到“答得稳”——检索 × 生成的一体化工程闭环

- Generated at: 2026-05-01 02:45:29
- Runner: `evals/week08/run_smoke_eval.py`
- Elapsed: `12.12 ms`
- Result: `PASS`

| case | status | evidence_count | abstain_reason | issues |
|---|---:|---:|---|---|
| `known_hit_edge_gateway` | PASS | 0 | no_retrieval_results | - |
| `lexical_keyword_firmware` | PASS | 0 | no_retrieval_results | - |
| `semantic_paraphrase` | PASS | 0 | no_retrieval_results | - |
| `product_line_filter` | PASS | 0 | no_retrieval_results | - |
| `no_answer` | PASS | 0 | no_retrieval_results | - |
| `permission_like_filter` | PASS | 0 | no_retrieval_results | - |

Notes:
- This is a Week8 smoke eval, not a Week11 LLM-as-judge harness.
- In an environment without PostgreSQL/pgvector data, answer cases may pass through structured abstain.
- A production-grade run should be executed through Docker Compose after index build.

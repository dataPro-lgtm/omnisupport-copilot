"""回归评测门禁测试

在 CI/CD 中运行，确保新 release 的评测指标不低于基线。
要求 RAG API 已运行（集成测试，跳过 unit 模式）。

运行方式:
    # 需要 RAG API 已在 localhost:8000 运行
    RAG_API_URL=http://localhost:8000 pytest tests/eval_regression/ -v
"""

import json
import os
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
EVAL_SET = PROJECT_ROOT / "evals" / "sets" / "workspace_qa_v1.jsonl"

RAG_API_URL = os.environ.get("RAG_API_URL", "")


# 没有设置 RAG_API_URL 时跳过（不影响本地 unit 测试）
pytestmark = pytest.mark.skipif(
    not RAG_API_URL,
    reason="Set RAG_API_URL env var to run eval regression tests"
)


# ── 回归门禁阈值（Week01 设为宽松，Week11 收紧）────────────────────────────

REGRESSION_THRESHOLDS = {
    "pass_rate": 0.0,           # Week01: 0, Week11: 0.8
    "avg_faithfulness": 0.0,    # Week01: 0, Week11: 0.6
    "avg_relevance": 0.0,       # Week01: 0, Week11: 0.5
    "avg_latency_ms": 30000,    # 30s 上限
}


@pytest.mark.asyncio
async def test_regression_gate():
    """完整评测回归门禁"""
    from evals.harness.eval_runner import EvalRunner

    release_id = os.environ.get("RELEASE_ID", "test-run")
    runner = EvalRunner(RAG_API_URL, release_id)
    summary = await runner.run(EVAL_SET, concurrency=3)

    assert summary.pass_rate >= REGRESSION_THRESHOLDS["pass_rate"], (
        f"Pass rate {summary.pass_rate:.1%} < threshold {REGRESSION_THRESHOLDS['pass_rate']:.1%}"
    )
    assert summary.avg_faithfulness >= REGRESSION_THRESHOLDS["avg_faithfulness"], (
        f"Faithfulness {summary.avg_faithfulness:.3f} below threshold"
    )
    assert summary.avg_latency_ms <= REGRESSION_THRESHOLDS["avg_latency_ms"], (
        f"Avg latency {summary.avg_latency_ms:.0f}ms exceeds limit"
    )


@pytest.mark.asyncio
async def test_health_before_eval():
    """eval 前先确认 API 健康"""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{RAG_API_URL}/health", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")

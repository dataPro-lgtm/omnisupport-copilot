import os
import sys
import types

from fastapi.testclient import TestClient


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "rag_api"))
os.environ.setdefault("OTEL_ENABLED", "false")

try:
    import asyncpg as _asyncpg  # noqa: F401
except ImportError:
    asyncpg_stub = types.ModuleType("asyncpg")

    class Pool:
        pass

    async def create_pool(*_args, **_kwargs):
        raise RuntimeError("asyncpg is not installed in the local contract test env")

    async def connect(*_args, **_kwargs):
        raise RuntimeError("asyncpg is not installed in the local contract test env")

    asyncpg_stub.Pool = Pool
    asyncpg_stub.create_pool = create_pool
    asyncpg_stub.connect = connect
    sys.modules["asyncpg"] = asyncpg_stub

from app.main import app


def test_week8_rag_answer_no_answer_contract():
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/rag/answer",
        json={
            "question": "What is the launch plan for a product not in the knowledge base?",
            "index_release_id": "index-week08-dev",
            "prompt_release_id": "prompt-week08-v1",
            "include_debug": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"] == []
    assert payload["evidence_ids"] == []
    assert payload["abstain_reason"] == "no_retrieval_results"
    assert payload["index_release_id"] == "index-week08-dev"
    assert payload["prompt_release_id"] == "prompt-week08-v1"
    assert payload["trace_id"]

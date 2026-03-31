"""RAG API Smoke Tests

不需要真实数据库/MinIO，用 TestClient 验证 API 骨架正确性。
Week01 DoD：这些测试必须本地 `pytest` 通过。
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """不启动真实依赖，直接测试 API 骨架"""
    import sys
    import os

    # 确保 rag_api 可导入
    sys.path.insert(0, str(
        __file__.replace("tests/integration/test_rag_api_smoke.py", "services/rag_api")
    ))

    # Patch 掉 OTel 初始化（测试环境不需要）
    os.environ.setdefault("OTEL_ENABLED", "false")

    from services.rag_api.app.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_required_fields(self, client):
        data = client.get("/health").json()
        assert "status" in data
        assert "service" in data
        assert "release_id" in data

    def test_health_service_name(self, client):
        data = client.get("/health").json()
        assert data["service"] == "rag_api"


class TestQueryEndpoint:
    def test_query_returns_200(self, client):
        resp = client.post("/api/v1/query", json={"query": "如何配置 Northstar Workspace？"})
        assert resp.status_code == 200

    def test_query_response_has_contract_fields(self, client):
        resp = client.post("/api/v1/query", json={"query": "EG-3000 接线图"})
        data = resp.json()
        # RAG Response Contract v1 必含字段
        assert "answer" in data
        assert "citations" in data
        assert "evidence_ids" in data
        assert "confidence" in data
        assert "release_id" in data
        assert "trace_id" in data
        assert "answer_grounded" in data

    def test_query_invalid_empty_query(self, client):
        resp = client.post("/api/v1/query", json={"query": ""})
        assert resp.status_code == 422  # Pydantic validation error

    def test_query_too_long_rejected(self, client):
        resp = client.post("/api/v1/query", json={"query": "x" * 3000})
        assert resp.status_code == 422


class TestAdminEndpoint:
    def test_release_info(self, client):
        resp = client.get("/api/v1/admin/release")
        assert resp.status_code == 200
        data = resp.json()
        assert "release_id" in data
        assert "data_release_id" in data
        assert "index_release_id" in data
        assert "prompt_release_id" in data


class TestRequestIdMiddleware:
    def test_response_has_request_id_header(self, client):
        resp = client.get("/health")
        assert "X-Request-ID" in resp.headers

    def test_request_id_propagated(self, client):
        custom_id = "test-req-12345"
        resp = client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.headers["X-Request-ID"] == custom_id

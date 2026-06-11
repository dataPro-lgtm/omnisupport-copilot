import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
TOOL_API_PATH = PROJECT_ROOT / "services" / "tool_api"
REGISTRY_PATH = PROJECT_ROOT / "analytics" / "metric_registry_v1.yml"


@pytest.fixture
def kpi_query_module():
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name, None)

    tool_api_path = str(TOOL_API_PATH)
    if tool_api_path in sys.path:
        sys.path.remove(tool_api_path)
    sys.path.insert(0, tool_api_path)

    from app import kpi_query

    yield kpi_query

    # Tool API and RAG API both use a top-level package named "app".
    # Clear it after these tests so full-suite collection is order-independent.
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name, None)


@pytest.mark.asyncio
async def test_query_support_kpis_rejects_unknown_metric(kpi_query_module):
    payload = {
        "actor_role": "instructor",
        "metrics": ["raw_sql_metric"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
    }

    result = await kpi_query_module.query_support_kpis(payload, registry_path=REGISTRY_PATH)

    assert result["allowed"] is False
    assert result["denial_code"] == "METRIC_DENIED"
    assert result["status"] == "denied"


@pytest.mark.asyncio
async def test_query_support_kpis_rejects_unsafe_dimension(kpi_query_module):
    payload = {
        "actor_role": "instructor",
        "metrics": ["ticket_count"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
        "dimensions": ["contact_email"],
    }

    result = await kpi_query_module.query_support_kpis(payload, registry_path=REGISTRY_PATH)

    assert result["allowed"] is False
    assert result["denial_code"] == "DIMENSION_DENIED"
    assert "dimension_policy" in result["policy_applied"]


@pytest.mark.asyncio
async def test_query_support_kpis_rejects_experimental_metric_without_ack(kpi_query_module):
    payload = {
        "actor_role": "instructor",
        "metrics": ["first_resolution_rate"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
    }

    result = await kpi_query_module.query_support_kpis(payload, registry_path=REGISTRY_PATH)

    assert result["allowed"] is False
    assert result["denial_code"] == "EXPERIMENTAL_METRIC_NOT_ACKNOWLEDGED"
    assert "experimental_metric_guard" in result["policy_applied"]


@pytest.mark.asyncio
async def test_query_support_kpis_support_ops_requires_org_scope(kpi_query_module):
    payload = {
        "actor_role": "support_ops",
        "metrics": ["ticket_count"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
    }

    result = await kpi_query_module.query_support_kpis(payload, registry_path=REGISTRY_PATH)

    assert result["allowed"] is False
    assert result["denial_code"] == "ORG_SCOPE_REQUIRED"
    assert "org_scope_required" in result["policy_applied"]


@pytest.mark.asyncio
async def test_query_support_kpis_uses_parameterized_safe_view(monkeypatch, kpi_query_module):
    captured = {}

    class FakeConnection:
        async def fetch(self, query, *params):
            captured["query"] = query
            captured["params"] = params
            return [
                {
                    "metric_date": "2026-04-24",
                    "metric_name": "ticket_count",
                    "product_line": "edge_gateway",
                    "metric_value": 3,
                    "data_release_id": "week05-dev-local",
                    "generated_at": "2026-04-24T10:00:00",
                }
            ]

        async def close(self):
            captured["closed"] = True

    async def fake_connect(dsn):
        captured["dsn"] = dsn
        return FakeConnection()

    monkeypatch.setattr(kpi_query_module.asyncpg, "connect", fake_connect)
    payload = {
        "actor_role": "instructor",
        "actor_id": "pytest",
        "metrics": ["ticket_count"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
        "trace_id": "trace-pytest",
        "purpose": "regression_eval",
        "dimensions": ["product_line"],
        "filters": {"priority": "p1_critical"},
        "limit": 10,
    }

    result = await kpi_query_module.query_support_kpis(payload, registry_path=REGISTRY_PATH)

    assert result["allowed"] is True
    assert result["status"] == "ok"
    assert result["audit_id"] == result["audit"]["audit_id"]
    assert result["trace_id"] == "trace-pytest"
    assert result["data_freshness"]["generated_at_max"] == "2026-04-24T10:00:00"
    assert "parameterized_sql" in result["policy_applied"]
    assert result["rows"][0]["metric_name"] == "ticket_count"
    assert "analytics.agent_tool_input_view" in captured["query"]
    assert "ticket_fact" not in captured["query"]
    assert captured["params"][0] == ["ticket_count"]
    assert captured["closed"] is True


@pytest.mark.asyncio
async def test_query_support_kpis_applies_org_scope_filter(monkeypatch, kpi_query_module):
    captured = {}

    class FakeConnection:
        async def fetch(self, query, *params):
            captured["query"] = query
            captured["params"] = params
            return []

        async def close(self):
            captured["closed"] = True

    async def fake_connect(dsn):
        captured["dsn"] = dsn
        return FakeConnection()

    monkeypatch.setattr(kpi_query_module.asyncpg, "connect", fake_connect)
    payload = {
        "actor_role": "support_ops",
        "actor_id": "ops-pytest",
        "actor_org_ids": ["org_001", "org_002"],
        "metrics": ["ticket_count"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
        "limit": 10,
    }

    result = await kpi_query_module.query_support_kpis(payload, registry_path=REGISTRY_PATH)

    assert result["allowed"] is True
    assert "org_id = any" in captured["query"]
    assert ["org_001", "org_002"] in captured["params"]
    assert "org_scope_filter" in result["policy_applied"]


@pytest.mark.asyncio
async def test_query_support_kpis_allows_experimental_metric_with_ack(monkeypatch, kpi_query_module):
    captured = {}

    class FakeConnection:
        async def fetch(self, query, *params):
            captured["query"] = query
            captured["params"] = params
            return [
                {
                    "metric_date": "2026-04-24",
                    "metric_name": "first_resolution_rate",
                    "metric_value": 0.75,
                    "data_release_id": "week05-dev-local",
                    "generated_at": "2026-04-24T10:00:00",
                }
            ]

        async def close(self):
            captured["closed"] = True

    async def fake_connect(dsn):
        captured["dsn"] = dsn
        return FakeConnection()

    monkeypatch.setattr(kpi_query_module.asyncpg, "connect", fake_connect)
    payload = {
        "actor_role": "instructor",
        "metrics": ["first_resolution_rate"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
        "include_experimental_metrics": True,
        "limit": 10,
    }

    result = await kpi_query_module.query_support_kpis(payload, registry_path=REGISTRY_PATH)

    assert result["allowed"] is True
    assert result["rows"][0]["metric_name"] == "first_resolution_rate"
    assert "experimental_metric_ack" in result["policy_applied"]

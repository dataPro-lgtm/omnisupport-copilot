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
        "dimensions": ["product_line"],
        "filters": {"priority": "p1_critical"},
        "limit": 10,
    }

    result = await kpi_query_module.query_support_kpis(payload, registry_path=REGISTRY_PATH)

    assert result["allowed"] is True
    assert result["rows"][0]["metric_name"] == "ticket_count"
    assert "analytics.agent_tool_input_view" in captured["query"]
    assert "ticket_fact" not in captured["query"]
    assert captured["params"][0] == ["ticket_count"]
    assert captured["closed"] is True

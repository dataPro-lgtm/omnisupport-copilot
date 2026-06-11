from pathlib import Path
from copy import deepcopy

from analytics.scripts.validate_metric_registry import load_registry, validate_registry

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_metric_registry_matches_safe_view_contract():
    registry = load_registry(PROJECT_ROOT / "analytics" / "metric_registry_v1.yml")
    result = validate_registry(registry)

    assert result["valid"], result["errors"]
    assert result["metric_count"] >= 11
    assert result["experimental_metric_count"] >= 1
    assert "first_resolution_rate" in result["metric_names"]
    assert "metric_value" in result["safe_view_columns"]


def test_metric_registry_rejects_missing_v11_metadata():
    registry = load_registry(PROJECT_ROOT / "analytics" / "metric_registry_v1.yml")
    broken = deepcopy(registry)
    broken["metrics"][0].pop("owner")

    result = validate_registry(broken)

    assert result["valid"] is False
    assert any("missing v1.1 field: owner" in error for error in result["errors"])

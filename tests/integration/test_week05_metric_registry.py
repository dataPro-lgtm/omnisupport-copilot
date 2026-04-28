from pathlib import Path

from analytics.scripts.validate_metric_registry import load_registry, validate_registry

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_metric_registry_matches_safe_view_contract():
    registry = load_registry(PROJECT_ROOT / "analytics" / "metric_registry_v1.yml")
    result = validate_registry(registry)

    assert result["valid"], result["errors"]
    assert result["metric_count"] >= 5
    assert "metric_value" in result["safe_view_columns"]

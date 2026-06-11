"""Validate Week05 metric registry against the dbt mart contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "analytics" / "metric_registry_v1.yml"
MARTS_DIR = PROJECT_ROOT / "analytics" / "models" / "marts"

SAFE_VIEW_COLUMNS = {
    "metric_date",
    "metric_name",
    "product_line",
    "priority",
    "org_id",
    "category",
    "metric_value",
    "data_release_id",
    "generated_at",
}
SAFE_VIEW_METRICS = {
    "ticket_count",
    "open_ticket_count",
    "p1_ticket_count",
    "sla_breach_count",
    "escalation_count",
    "avg_backlog_age_days",
    "avg_first_response_minutes",
    "avg_handle_time_minutes",
    "first_resolution_rate",
    "escalation_rate",
    "sla_breach_rate",
}
REQUIRED_METRIC_FIELDS_V11 = {
    "business_name_zh",
    "business_definition_zh",
    "owner",
    "metric_type",
    "formula",
    "unit",
    "sensitivity",
    "definition_status",
    "version",
    "quality_tests",
}
ALLOWED_AGGREGATIONS = {"sum", "avg", "min", "max"}
ALLOWED_METRIC_TYPES = {"count", "average", "ratio"}
ALLOWED_SENSITIVITY = {"low", "medium", "high"}
ALLOWED_DEFINITION_STATUS = {"production", "experimental_proxy"}


def load_registry(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("metric registry must be a YAML mapping")
    return data


def validate_registry(registry: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    required = [
        "version",
        "registry_id",
        "source_model",
        "safe_view",
        "time_dimension",
        "measure_column",
        "max_window_days",
        "allowed_dimensions",
        "allowed_filters",
        "allowed_roles",
        "metrics",
    ]
    for field in required:
        if field not in registry:
            errors.append(f"missing required field: {field}")

    source_model = registry.get("source_model")
    safe_view = registry.get("safe_view")
    if source_model and not (MARTS_DIR / f"{source_model}.sql").exists():
        errors.append(f"source_model not found in dbt marts: {source_model}")
    if safe_view and not (MARTS_DIR / f"{safe_view}.sql").exists():
        errors.append(f"safe_view not found in dbt marts: {safe_view}")

    for field in registry.get("allowed_dimensions", []):
        if field not in SAFE_VIEW_COLUMNS:
            errors.append(f"allowed dimension is not exposed by safe view: {field}")
    for field in registry.get("allowed_filters", []):
        if field not in SAFE_VIEW_COLUMNS:
            errors.append(f"allowed filter is not exposed by safe view: {field}")

    time_dimension = registry.get("time_dimension")
    measure_column = registry.get("measure_column")
    if time_dimension not in SAFE_VIEW_COLUMNS:
        errors.append(f"time_dimension is not exposed by safe view: {time_dimension}")
    if measure_column not in SAFE_VIEW_COLUMNS:
        errors.append(f"measure_column is not exposed by safe view: {measure_column}")

    metrics = registry.get("metrics", [])
    seen_names: set[str] = set()
    experimental_count = 0
    if not isinstance(metrics, list) or not metrics:
        errors.append("metrics must be a non-empty list")
    else:
        registry_roles = set(registry.get("allowed_roles", []))
        for idx, metric in enumerate(metrics):
            if not isinstance(metric, dict):
                errors.append(f"metric[{idx}] must be a mapping")
                continue
            name = metric.get("name")
            if not name:
                errors.append(f"metric[{idx}] missing name")
            elif name in seen_names:
                errors.append(f"duplicate metric name: {name}")
            else:
                seen_names.add(name)
                if name not in SAFE_VIEW_METRICS:
                    errors.append(f"metric is not allowed by safe view metric list: {name}")

            for field in REQUIRED_METRIC_FIELDS_V11:
                if field not in metric:
                    errors.append(f"metric[{idx}] missing v1.1 field: {field}")

            if metric.get("aggregation") not in ALLOWED_AGGREGATIONS:
                errors.append(f"metric[{idx}] has unsupported aggregation: {metric.get('aggregation')}")
            if metric.get("metric_type") not in ALLOWED_METRIC_TYPES:
                errors.append(f"metric[{idx}] has unsupported metric_type: {metric.get('metric_type')}")
            if metric.get("sensitivity") not in ALLOWED_SENSITIVITY:
                errors.append(f"metric[{idx}] has unsupported sensitivity: {metric.get('sensitivity')}")
            if metric.get("definition_status") not in ALLOWED_DEFINITION_STATUS:
                errors.append(
                    f"metric[{idx}] has unsupported definition_status: {metric.get('definition_status')}"
                )
            if metric.get("definition_status") == "experimental_proxy":
                experimental_count += 1
            if metric.get("metric_type") == "ratio" and (
                not metric.get("numerator") or not metric.get("denominator")
            ):
                errors.append(f"metric[{idx}] ratio metric must declare numerator and denominator")
            quality_tests = metric.get("quality_tests")
            if not isinstance(quality_tests, list) or not quality_tests:
                errors.append(f"metric[{idx}] quality_tests must be a non-empty list")

            metric_roles = set(metric.get("allowed_roles", []))
            if not metric_roles:
                errors.append(f"metric[{idx}] missing allowed_roles")
            elif not metric_roles.issubset(registry_roles):
                errors.append(f"metric[{idx}] has roles outside registry allowed_roles")

    return {
        "valid": not errors,
        "errors": errors,
        "metric_count": len(metrics) if isinstance(metrics, list) else 0,
        "experimental_metric_count": experimental_count if isinstance(metrics, list) else 0,
        "metric_names": sorted(seen_names) if isinstance(metrics, list) else [],
        "registry_version": registry.get("registry_version"),
        "safe_view_columns": sorted(SAFE_VIEW_COLUMNS),
        "safe_view_metrics": sorted(SAFE_VIEW_METRICS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Week05 metric registry.")
    parser.add_argument("--path", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    result = validate_registry(load_registry(args.path))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "VALID" if result["valid"] else "INVALID"
        print(f"metric_registry_v1: {status}")
        for error in result["errors"]:
            print(f"- {error}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

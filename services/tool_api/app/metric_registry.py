"""Week05 metric registry loader for governed KPI tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config import settings


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    aggregation: str
    allowed_roles: frozenset[str]


@dataclass(frozen=True)
class MetricRegistry:
    registry_id: str
    source_model: str
    safe_view: str
    time_dimension: str
    measure_column: str
    max_window_days: int
    allowed_dimensions: frozenset[str]
    allowed_filters: frozenset[str]
    allowed_roles: frozenset[str]
    metrics: dict[str, MetricDefinition]


def load_metric_registry(path: str | Path | None = None) -> MetricRegistry:
    registry_path = Path(path or settings.metric_registry_path)
    if not registry_path.exists():
        local_file = Path(__file__).resolve()
        if len(local_file.parents) > 3:
            fallback = local_file.parents[3] / "analytics" / "metric_registry_v1.yml"
            if fallback.exists():
                registry_path = fallback
    with registry_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    metrics = {
        item["name"]: MetricDefinition(
            name=item["name"],
            aggregation=item["aggregation"],
            allowed_roles=frozenset(item.get("allowed_roles", [])),
        )
        for item in data.get("metrics", [])
    }

    return MetricRegistry(
        registry_id=data["registry_id"],
        source_model=data["source_model"],
        safe_view=data["safe_view"],
        time_dimension=data["time_dimension"],
        measure_column=data["measure_column"],
        max_window_days=int(data["max_window_days"]),
        allowed_dimensions=frozenset(data.get("allowed_dimensions", [])),
        allowed_filters=frozenset(data.get("allowed_filters", [])),
        allowed_roles=frozenset(data.get("allowed_roles", [])),
        metrics=metrics,
    )


def registry_to_dict(registry: MetricRegistry) -> dict[str, Any]:
    return {
        "registry_id": registry.registry_id,
        "source_model": registry.source_model,
        "safe_view": registry.safe_view,
        "time_dimension": registry.time_dimension,
        "measure_column": registry.measure_column,
        "max_window_days": registry.max_window_days,
        "allowed_dimensions": sorted(registry.allowed_dimensions),
        "allowed_filters": sorted(registry.allowed_filters),
        "allowed_roles": sorted(registry.allowed_roles),
        "metrics": sorted(registry.metrics),
    }

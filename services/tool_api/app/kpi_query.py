"""Governed Week05 KPI query runtime.

This module deliberately does not accept raw SQL. It validates every request
against the tool contract and metric registry, then emits parameterized SQL
against the dbt-built safe view.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg
import jsonschema

from app.config import settings
from app.metric_registry import MetricRegistry, load_metric_registry

LOCAL_FILE = Path(__file__).resolve()
TOOL_CONTRACT_CANDIDATES = [
    Path("/workspace/contracts/tools/tools/query_support_kpis_v1.json"),
    LOCAL_FILE.parents[3] / "contracts" / "tools" / "tools" / "query_support_kpis_v1.json"
    if len(LOCAL_FILE.parents) > 3
    else None,
]
SAFE_COLUMNS = {
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


def _load_input_schema() -> dict[str, Any]:
    contract_path = next(
        path for path in TOOL_CONTRACT_CANDIDATES if path is not None and path.exists()
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    return contract["input_schema"]


def _normalize_dsn(database_url: str) -> str:
    return (
        database_url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg2://", "postgresql://")
    )


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _audit(
    payload: dict[str, Any],
    registry: MetricRegistry | None,
    row_count: int = 0,
) -> dict[str, Any]:
    return {
        "tool_name": "query_support_kpis_v1",
        "registry_id": registry.registry_id if registry else "unloaded",
        "actor_role": payload.get("actor_role"),
        "actor_id": payload.get("actor_id"),
        "metrics": payload.get("metrics", []),
        "dimensions": payload.get("dimensions", []),
        "filters": payload.get("filters", {}),
        "date_from": payload.get("date_from"),
        "date_to": payload.get("date_to"),
        "row_count": row_count,
        "release_id": settings.release_id,
    }


def _deny(
    code: str,
    message: str,
    payload: dict[str, Any],
    registry: MetricRegistry | None = None,
) -> dict[str, Any]:
    return {
        "allowed": False,
        "rows": [],
        "denial_code": code,
        "message": message,
        "audit": _audit(payload, registry),
    }


def _validate_request(payload: dict[str, Any], registry: MetricRegistry) -> dict[str, Any] | None:
    try:
        jsonschema.validate(
            instance=payload,
            schema=_load_input_schema(),
            format_checker=jsonschema.FormatChecker(),
        )
    except jsonschema.ValidationError as exc:
        return _deny("SCHEMA_VALIDATION_FAILED", exc.message, payload, registry)

    actor_role = payload["actor_role"]
    if actor_role not in registry.allowed_roles:
        return _deny("ROLE_DENIED", f"role is not allowed: {actor_role}", payload, registry)

    requested_metrics = payload["metrics"]
    denied_metrics = [
        name
        for name in requested_metrics
        if name not in registry.metrics or actor_role not in registry.metrics[name].allowed_roles
    ]
    if denied_metrics:
        return _deny(
            "METRIC_DENIED",
            f"metrics are not registered or not role-allowed: {', '.join(denied_metrics)}",
            payload,
            registry,
        )

    dimensions = payload.get("dimensions", [])
    denied_dimensions = [name for name in dimensions if name not in registry.allowed_dimensions]
    if denied_dimensions:
        return _deny(
            "DIMENSION_DENIED",
            f"dimensions are not safe: {', '.join(denied_dimensions)}",
            payload,
            registry,
        )

    filters = payload.get("filters", {})
    denied_filters = [name for name in filters if name not in registry.allowed_filters]
    if denied_filters:
        return _deny(
            "FILTER_DENIED",
            f"filters are not safe: {', '.join(denied_filters)}",
            payload,
            registry,
        )

    date_from = _parse_date(payload["date_from"])
    date_to = _parse_date(payload["date_to"])
    if date_to < date_from:
        return _deny("SCHEMA_VALIDATION_FAILED", "date_to must be on or after date_from", payload, registry)
    if (date_to - date_from).days > registry.max_window_days:
        return _deny(
            "WINDOW_TOO_LARGE",
            f"date window exceeds {registry.max_window_days} days",
            payload,
            registry,
        )

    return None


def _build_query(payload: dict[str, Any], registry: MetricRegistry) -> tuple[str, list[Any]]:
    selected_dimensions = payload.get("dimensions", [])
    output_columns = ["metric_date", "metric_name", *selected_dimensions, "metric_value", "data_release_id"]
    invalid_columns = [column for column in output_columns if column not in SAFE_COLUMNS]
    if invalid_columns:
        raise ValueError(f"unsafe output columns: {', '.join(invalid_columns)}")

    params: list[Any] = [payload["metrics"], _parse_date(payload["date_from"]), _parse_date(payload["date_to"])]
    where = [
        "metric_name = any($1::text[])",
        "metric_date between $2::date and $3::date",
    ]
    for field, value in payload.get("filters", {}).items():
        params.append([str(item) for item in value] if isinstance(value, list) else [str(value)])
        where.append(f"{field} = any(${len(params)}::text[])")

    params.append(int(payload.get("limit", 100)))
    columns_sql = ", ".join(output_columns)
    where_sql = " and ".join(where)
    order_sql = ", ".join(output_columns[:-2])

    query = f"""
        select {columns_sql}
        from analytics.{registry.safe_view}
        where {where_sql}
        order by {order_sql}
        limit ${len(params)}
    """
    return query, params


async def query_support_kpis(
    payload: dict[str, Any],
    *,
    database_url: str | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    registry = load_metric_registry(registry_path)
    denial = _validate_request(payload, registry)
    if denial:
        return denial

    try:
        query, params = _build_query(payload, registry)
        connection = await asyncpg.connect(_normalize_dsn(database_url or settings.database_url))
        try:
            records = await connection.fetch(query, *params)
        finally:
            await connection.close()
    except Exception as exc:
        return _deny("DB_UNAVAILABLE", str(exc), payload, registry)

    rows = [{key: _json_safe(value) for key, value in record.items()} for record in records]
    return {
        "allowed": True,
        "rows": rows,
        "denial_code": None,
        "message": None,
        "audit": _audit(payload, registry, row_count=len(rows)),
    }


EXAMPLES: dict[str, dict[str, Any]] = {
    "valid": {
        "actor_role": "instructor",
        "actor_id": "local-demo",
        "metrics": ["ticket_count", "open_ticket_count"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
        "dimensions": ["product_line", "priority"],
        "filters": {},
        "limit": 20,
    },
    "bad_role": {
        "actor_role": "viewer",
        "metrics": ["ticket_count"],
        "date_from": "2026-01-01",
        "date_to": "2026-01-31",
    },
    "bad_metric": {
        "actor_role": "instructor",
        "metrics": ["raw_sql_revenue"],
        "date_from": "2026-01-01",
        "date_to": "2026-01-31",
    },
}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run a governed Week05 KPI query.")
    parser.add_argument("--example", choices=sorted(EXAMPLES), default="valid")
    parser.add_argument("--payload", help="JSON payload. Overrides --example when provided.")
    args = parser.parse_args()

    payload = json.loads(args.payload) if args.payload else EXAMPLES[args.example]
    result = await query_support_kpis(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

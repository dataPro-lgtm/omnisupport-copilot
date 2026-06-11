"""Governed Week05 KPI query runtime.

This module deliberately does not accept raw SQL. It validates every request
against the tool contract and metric registry, then emits parameterized SQL
against the dbt-built safe view.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import uuid
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
BASE_POLICIES = ["tool_contract", "metric_registry", "safe_view", "parameterized_sql"]


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


def _query_fingerprint(payload: dict[str, Any]) -> str:
    stable = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def _data_freshness(rows: list[dict[str, Any]], registry: MetricRegistry | None) -> dict[str, Any]:
    generated_values = [
        row.get("generated_at")
        for row in rows
        if row.get("generated_at") is not None
    ]
    release_values = [
        row.get("data_release_id")
        for row in rows
        if row.get("data_release_id") is not None
    ]
    return {
        "generated_at_max": max(generated_values) if generated_values else None,
        "release_id": release_values[0] if release_values else settings.release_id,
        "registry_id": registry.registry_id if registry else "unloaded",
        "registry_version": registry.registry_version if registry else None,
    }


def _audit(
    payload: dict[str, Any],
    registry: MetricRegistry | None,
    row_count: int = 0,
    *,
    policy_applied: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "audit_id": str(uuid.uuid4()),
        "tool_name": "query_support_kpis_v1",
        "registry_id": registry.registry_id if registry else "unloaded",
        "registry_version": registry.registry_version if registry else None,
        "actor_role": payload.get("actor_role"),
        "actor_id": payload.get("actor_id"),
        "trace_id": payload.get("trace_id"),
        "purpose": payload.get("purpose", "classroom_demo"),
        "metrics": payload.get("metrics", []),
        "dimensions": payload.get("dimensions", []),
        "filters": payload.get("filters", {}),
        "actor_org_ids": payload.get("actor_org_ids", []),
        "date_from": payload.get("date_from"),
        "date_to": payload.get("date_to"),
        "row_count": row_count,
        "release_id": settings.release_id,
        "safe_view": registry.safe_view if registry else None,
        "query_fingerprint": _query_fingerprint(payload),
        "policy_applied": policy_applied or [],
    }


def _deny(
    code: str,
    message: str,
    payload: dict[str, Any],
    registry: MetricRegistry | None = None,
    *,
    policy_applied: list[str] | None = None,
    status: str = "denied",
) -> dict[str, Any]:
    audit = _audit(payload, registry, policy_applied=policy_applied or [])
    return {
        "allowed": False,
        "status": status,
        "rows": [],
        "denial_code": code,
        "message": message,
        "audit_id": audit["audit_id"],
        "trace_id": audit["trace_id"],
        "policy_applied": audit["policy_applied"],
        "data_freshness": _data_freshness([], registry),
        "audit": audit,
    }


def _validate_request(payload: dict[str, Any], registry: MetricRegistry) -> dict[str, Any] | None:
    try:
        jsonschema.validate(
            instance=payload,
            schema=_load_input_schema(),
            format_checker=jsonschema.FormatChecker(),
        )
    except jsonschema.ValidationError as exc:
        return _deny("SCHEMA_VALIDATION_FAILED", exc.message, payload, registry, policy_applied=["tool_contract"])

    actor_role = payload["actor_role"]
    if actor_role not in registry.allowed_roles:
        return _deny(
            "ROLE_DENIED",
            f"role is not allowed: {actor_role}",
            payload,
            registry,
            policy_applied=["tool_contract", "metric_registry", "role_policy"],
        )

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
            policy_applied=["tool_contract", "metric_registry"],
        )

    experimental_metrics = [
        name
        for name in requested_metrics
        if registry.metrics[name].definition_status == "experimental_proxy"
    ]
    if experimental_metrics and not payload.get("include_experimental_metrics", False):
        return _deny(
            "EXPERIMENTAL_METRIC_NOT_ACKNOWLEDGED",
            (
                "experimental_proxy metrics require include_experimental_metrics=true: "
                + ", ".join(experimental_metrics)
            ),
            payload,
            registry,
            policy_applied=["tool_contract", "metric_registry", "experimental_metric_guard"],
        )

    dimensions = payload.get("dimensions", [])
    denied_dimensions = [name for name in dimensions if name not in registry.allowed_dimensions]
    if denied_dimensions:
        return _deny(
            "DIMENSION_DENIED",
            f"dimensions are not safe: {', '.join(denied_dimensions)}",
            payload,
            registry,
            policy_applied=["tool_contract", "metric_registry", "dimension_policy"],
        )

    filters = payload.get("filters", {})
    denied_filters = [name for name in filters if name not in registry.allowed_filters]
    if denied_filters:
        return _deny(
            "FILTER_DENIED",
            f"filters are not safe: {', '.join(denied_filters)}",
            payload,
            registry,
            policy_applied=["tool_contract", "metric_registry", "filter_policy"],
        )

    if actor_role == "support_ops" and not payload.get("actor_org_ids"):
        return _deny(
            "ORG_SCOPE_REQUIRED",
            "support_ops queries must include actor_org_ids in classroom v1.1 policy",
            payload,
            registry,
            policy_applied=["tool_contract", "metric_registry", "org_scope_required"],
        )

    date_from = _parse_date(payload["date_from"])
    date_to = _parse_date(payload["date_to"])
    if date_to < date_from:
        return _deny(
            "SCHEMA_VALIDATION_FAILED",
            "date_to must be on or after date_from",
            payload,
            registry,
            policy_applied=["tool_contract"],
        )
    if (date_to - date_from).days > registry.max_window_days:
        return _deny(
            "WINDOW_TOO_LARGE",
            f"date window exceeds {registry.max_window_days} days",
            payload,
            registry,
            policy_applied=["tool_contract", "metric_registry", "window_policy"],
        )

    return None


def _build_query(payload: dict[str, Any], registry: MetricRegistry) -> tuple[str, list[Any]]:
    selected_dimensions = payload.get("dimensions", [])
    output_columns = [
        "metric_date",
        "metric_name",
        *selected_dimensions,
        "metric_value",
        "data_release_id",
        "generated_at",
    ]
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
    if payload.get("actor_role") != "admin" and payload.get("actor_org_ids"):
        params.append([str(item) for item in payload["actor_org_ids"]])
        where.append(f"org_id = any(${len(params)}::text[])")

    params.append(int(payload.get("limit", 100)))
    columns_sql = ", ".join(output_columns)
    where_sql = " and ".join(where)
    order_sql = ", ".join(["metric_date", "metric_name", *selected_dimensions])

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
        return _deny(
            "DB_UNAVAILABLE",
            str(exc),
            payload,
            registry,
            policy_applied=BASE_POLICIES,
            status="error",
        )

    rows = [{key: _json_safe(value) for key, value in record.items()} for record in records]
    policy_applied = list(BASE_POLICIES)
    if payload.get("actor_role") != "admin" and payload.get("actor_org_ids"):
        policy_applied.append("org_scope_filter")
    if any(registry.metrics[name].definition_status == "experimental_proxy" for name in payload["metrics"]):
        policy_applied.append("experimental_metric_ack")
    audit = _audit(payload, registry, row_count=len(rows), policy_applied=policy_applied)
    return {
        "allowed": True,
        "status": "ok",
        "rows": rows,
        "denial_code": None,
        "message": None,
        "audit_id": audit["audit_id"],
        "trace_id": audit["trace_id"],
        "policy_applied": audit["policy_applied"],
        "data_freshness": _data_freshness(rows, registry),
        "audit": audit,
    }


EXAMPLES: dict[str, dict[str, Any]] = {
    "valid": {
        "actor_role": "instructor",
        "actor_id": "local-demo",
        "trace_id": "trace-week05-local-demo",
        "purpose": "classroom_demo",
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
    "bad_experimental": {
        "actor_role": "instructor",
        "metrics": ["first_resolution_rate"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
    },
    "bad_org_scope": {
        "actor_role": "support_ops",
        "metrics": ["ticket_count"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
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

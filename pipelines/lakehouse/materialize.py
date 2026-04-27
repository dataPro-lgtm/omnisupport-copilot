"""Materialize Week04 core PostgreSQL tables into Iceberg."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pyarrow as pa

from pipelines.lakehouse.catalog import CORE_TABLES, ensure_core_tables, load_lakehouse_catalog
from pipelines.lakehouse.settings import LakehouseSettings

TABLE_QUERIES = {
    "bronze.raw_ticket_event": """
        SELECT DISTINCT ON (source_id, source_fingerprint)
            event_id,
            source_id,
            manifest_id,
            ingest_batch_id,
            raw_payload::text AS raw_payload,
            schema_version,
            license_tag,
            pii_level::text AS pii_level,
            ingest_ts,
            source_fingerprint
        FROM raw_ticket_event
        ORDER BY source_id, source_fingerprint, ingest_ts DESC
    """,
    "bronze.raw_doc_asset": """
        SELECT
            source_id,
            asset_type,
            raw_object_path,
            manifest_id,
            ingest_batch_id,
            license_tag,
            product_line::text AS product_line,
            doc_version,
            page_count,
            source_fingerprint,
            pii_level::text AS pii_level,
            quality_gate::text AS quality_gate,
            ingest_ts
        FROM raw_doc_asset
        ORDER BY source_id
    """,
    "silver.ticket_fact": """
        SELECT
            ticket_id,
            customer_id,
            org_id,
            status::text AS status,
            priority::text AS priority,
            category,
            product_line::text AS product_line,
            product_version,
            subject,
            error_codes,
            asset_ids,
            assignee_id,
            sla_tier::text AS sla_tier,
            sla_due_at,
            created_at,
            updated_at,
            resolved_at,
            pii_level::text AS pii_level,
            pii_redacted,
            data_release_id,
            ingest_batch_id
        FROM ticket_fact
        ORDER BY ticket_id
    """,
    "silver.knowledge_doc": """
        SELECT
            doc_id,
            source_id,
            asset_type,
            product_line::text AS product_line,
            doc_version,
            title,
            language,
            page_count,
            section_count,
            chunk_count,
            source_url,
            source_fingerprint,
            license_tag,
            pii_level::text AS pii_level,
            quality_gate::text AS quality_gate,
            data_release_id,
            indexed_at
        FROM knowledge_doc
        ORDER BY doc_id
    """,
}


async def fetch_source_records(table_name: str, settings: LakehouseSettings) -> list[dict]:
    import asyncpg

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(TABLE_QUERIES[table_name])
    finally:
        await conn.close()
    return [dict(row) for row in rows]


def rows_to_arrow(rows: list[dict], schema: pa.Schema) -> pa.Table:
    normalized: list[dict] = []
    for row in rows:
        normalized.append({_field.name: _normalize_value(row.get(_field.name)) for _field in schema})
    return pa.Table.from_pylist(normalized, schema=schema)


def _normalize_value(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return value


async def materialize_tables(
    tables: Iterable[str],
    dry_run: bool = False,
    plan: bool = False,
    report_json: Path | None = None,
) -> dict:
    settings = LakehouseSettings.from_env()
    catalog = None if plan else load_lakehouse_catalog(settings)
    ensured = {} if plan else ensure_core_tables(catalog, settings, tables)

    results: dict[str, dict] = {}
    for table_name in tables:
        rows = await fetch_source_records(table_name, settings)
        result = {
            "source_rows": len(rows),
            "write_mode": _write_mode(table_name),
            "action": "plan" if plan else "dry_run" if dry_run else "overwrite",
        }
        if not plan and not dry_run:
            table = catalog.load_table(table_name)
            arrow_schema = table.schema().as_arrow()
            arrow_table = rows_to_arrow(rows, arrow_schema)
            if arrow_table.num_rows == 0:
                result["snapshot_id"] = None
                result["note"] = "source table is empty; table ensured but no snapshot written"
            else:
                table.overwrite(
                    arrow_table,
                    snapshot_properties={
                        "omni.week": "week04",
                        "omni.data_release_id": settings.data_release_id,
                        "omni.ingest_batch_id": settings.ingest_batch_id,
                        "omni.write_mode": result["write_mode"],
                    },
                )
                refreshed = catalog.load_table(table_name)
                snapshot = refreshed.current_snapshot()
                result["snapshot_id"] = snapshot.snapshot_id if snapshot else None
        if table_name in ensured:
            result["location"] = ensured[table_name]["location"]
        results[table_name] = result

    payload = {
        "report_version": "week04_lakehouse_materialization_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_release_id": settings.data_release_id,
        "ingest_batch_id": settings.ingest_batch_id,
        "dry_run": dry_run,
        "plan": plan,
        "tables": results,
    }
    if report_json:
        _write_json(report_json, payload)
    return payload


def _write_mode(table_name: str) -> str:
    if table_name.startswith("bronze."):
        return "deduped_full_refresh"
    return "deterministic_full_refresh"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")


def _resolve_tables(args) -> list[str]:
    if args.all_core:
        return list(CORE_TABLES)
    if args.table:
        if args.table not in CORE_TABLES:
            raise SystemExit(f"Unsupported Week04 core table: {args.table}")
        return [args.table]
    raise SystemExit("Use --all-core or --table <namespace.table>.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize Week04 core Iceberg tables")
    parser.add_argument("--all-core", action="store_true", help="materialize the four Week04 core tables")
    parser.add_argument("--table", choices=CORE_TABLES, help="materialize one table")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--report-json", type=Path, default=None)
    args = parser.parse_args()

    payload = asyncio.run(
        materialize_tables(
            _resolve_tables(args),
            dry_run=args.dry_run,
            plan=args.plan,
            report_json=args.report_json,
        )
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

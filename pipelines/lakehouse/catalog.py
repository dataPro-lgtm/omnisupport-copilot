"""Week04 PyIceberg catalog helpers."""

from __future__ import annotations

import argparse
import json
from typing import Iterable

import pyarrow as pa

from pipelines.lakehouse.iceberg_schemas import BRONZE_SCHEMAS, SILVER_SCHEMAS
from pipelines.lakehouse.settings import LakehouseSettings

CORE_TABLES = (
    "bronze.raw_ticket_event",
    "bronze.raw_doc_asset",
    "silver.ticket_fact",
    "silver.knowledge_doc",
)

TABLE_SCHEMA_SOURCES = {
    "bronze.raw_ticket_event": BRONZE_SCHEMAS["raw_ticket_event"],
    "bronze.raw_doc_asset": BRONZE_SCHEMAS["raw_doc_asset"],
    "silver.ticket_fact": SILVER_SCHEMAS["ticket_fact"],
    "silver.knowledge_doc": SILVER_SCHEMAS["knowledge_doc"],
}


def load_lakehouse_catalog(settings: LakehouseSettings | None = None):
    from pyiceberg.catalog import load_catalog

    settings = settings or LakehouseSettings.from_env()
    return load_catalog(settings.catalog_name, **settings.as_catalog_properties())


def ensure_lakehouse_bucket(settings: LakehouseSettings | None = None) -> dict:
    settings = settings or LakehouseSettings.from_env()
    import boto3
    from botocore.client import Config

    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        config=Config(s3={"addressing_style": "path"}),
    )
    bucket = settings.warehouse_bucket
    try:
        client.create_bucket(Bucket=bucket)
    except Exception as exc:
        if "BucketAlready" not in str(exc) and "already" not in str(exc).lower():
            raise
    client.head_bucket(Bucket=bucket)
    return {"bucket": bucket, "status": "available"}


def ensure_namespaces(catalog, settings: LakehouseSettings | None = None) -> list[str]:
    settings = settings or LakehouseSettings.from_env()
    created_or_existing: list[str] = []
    for namespace in (settings.bronze_namespace, settings.silver_namespace):
        try:
            if not catalog.namespace_exists(namespace):
                catalog.create_namespace(namespace)
        except AttributeError:
            try:
                catalog.create_namespace(namespace)
            except Exception:
                pass
        except Exception as exc:
            if "already" not in str(exc).lower() and "exists" not in str(exc).lower():
                raise
        created_or_existing.append(namespace)
    return created_or_existing


def schema_for_table(table_name: str) -> pa.Schema:
    source = TABLE_SCHEMA_SOURCES[table_name]
    return pa.schema([_field_to_arrow(field) for field in source["fields"]])


def _field_to_arrow(field: tuple[str, str, str]) -> pa.Field:
    name, type_name, doc = field
    nullable = "NOT NULL" not in doc and "NOT NULL" not in type_name
    clean_type = type_name.replace("NOT NULL", "").strip()
    return pa.field(name, _type_to_arrow(clean_type), nullable=nullable)


def _type_to_arrow(type_name: str) -> pa.DataType:
    match type_name:
        case "string":
            return pa.string()
        case "int":
            return pa.int32()
        case "long":
            return pa.int64()
        case "double":
            return pa.float64()
        case "boolean":
            return pa.bool_()
        case "timestamp":
            return pa.timestamp("us", tz="UTC")
        case "date":
            return pa.date32()
        case "list<string>":
            return pa.list_(pa.string())
        case _:
            return pa.string()


def ensure_core_tables(
    catalog=None,
    settings: LakehouseSettings | None = None,
    tables: Iterable[str] = CORE_TABLES,
) -> dict[str, dict]:
    settings = settings or LakehouseSettings.from_env()
    catalog = catalog or load_lakehouse_catalog(settings)
    ensure_namespaces(catalog, settings)

    results: dict[str, dict] = {}
    for table_name in tables:
        schema = schema_for_table(table_name)
        location = _table_location(settings, table_name)
        table = catalog.create_table_if_not_exists(
            identifier=table_name,
            schema=schema,
            location=location,
            properties={
                "write.format.default": "parquet",
                "omni.week": "week04",
                "omni.write_mode": _write_mode(table_name),
            },
        )
        results[table_name] = {
            "location": table.location(),
            "schema_fields": len(table.schema().fields),
            "exists": True,
        }
    return results


def _table_location(settings: LakehouseSettings, table_name: str) -> str:
    namespace, table = table_name.split(".", 1)
    return f"{settings.warehouse.rstrip('/')}/{namespace}.db/{table}"


def _write_mode(table_name: str) -> str:
    if table_name.startswith("bronze."):
        return "deterministic_full_refresh_from_deduped_source"
    return "deterministic_full_refresh"


def smoke_check() -> dict:
    settings = LakehouseSettings.from_env()
    errors = settings.validate()
    if errors:
        return {"ok": False, "errors": errors}
    bucket = ensure_lakehouse_bucket(settings)
    catalog = load_lakehouse_catalog(settings)
    namespaces = ensure_namespaces(catalog, settings)
    tables = ensure_core_tables(catalog, settings)
    return {
        "ok": True,
        "catalog": settings.catalog_name,
        "bucket": bucket,
        "namespaces": namespaces,
        "tables": tables,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Week04 PyIceberg catalog smoke/ensure")
    parser.add_argument("--smoke", action="store_true", help="load catalog, ensure bucket, namespaces, tables")
    parser.add_argument("--ensure", action="store_true", help="ensure namespaces and core tables")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    if args.smoke or args.ensure:
        payload = smoke_check()
    else:
        payload = {
            "ok": True,
            "core_tables": list(CORE_TABLES),
            "settings": LakehouseSettings.from_env().to_safe_dict(),
        }

    if args.json or args.smoke or args.ensure:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

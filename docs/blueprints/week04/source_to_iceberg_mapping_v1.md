# Week04 Source to Iceberg Mapping v1

This mapping is based on:
- `infra/migrations/001_init.sql`
- `pipelines/ingestion/ticket_ingest.py`
- `pipelines/ingestion/doc_ingest.py`
- `pipelines/lakehouse/iceberg_schemas.py`

## `bronze.raw_ticket_event`

| Iceberg field | PostgreSQL source | Notes |
|---|---|---|
| `event_id` | `raw_ticket_event.event_id` | PostgreSQL default UUID is not stable across duplicate ingest attempts. |
| `source_id` | `raw_ticket_event.source_id` | Required. |
| `manifest_id` | `raw_ticket_event.manifest_id` | Current ingest approximates this from source id. |
| `ingest_batch_id` | `raw_ticket_event.ingest_batch_id` | Batch tracking. |
| `raw_payload` | `raw_ticket_event.raw_payload::text` | JSONB serialized as string for Iceberg portability. |
| `schema_version` | `raw_ticket_event.schema_version` | Contract trace. |
| `license_tag` | `raw_ticket_event.license_tag` | Compliance trace. |
| `pii_level` | `raw_ticket_event.pii_level::text` | Enum normalized to string. |
| `ingest_ts` | `raw_ticket_event.ingest_ts` | Time field. |
| `source_fingerprint` | `raw_ticket_event.source_fingerprint` | Deterministic dedupe key input. |

Deduplication: `source_id + source_fingerprint`, keeping the latest `ingest_ts`.

## `bronze.raw_doc_asset`

| Iceberg field | PostgreSQL source | Notes |
|---|---|---|
| `source_id` | `raw_doc_asset.source_id` | Stable asset key. |
| `asset_type` | `raw_doc_asset.asset_type` | Document type. |
| `raw_object_path` | `raw_doc_asset.raw_object_path` | MinIO or source URI. |
| `manifest_id` | `raw_doc_asset.manifest_id` | Source manifest trace. |
| `ingest_batch_id` | `raw_doc_asset.ingest_batch_id` | Batch tracking. |
| `license_tag` | `raw_doc_asset.license_tag` | Compliance trace. |
| `product_line` | `raw_doc_asset.product_line::text` | Enum normalized to string. |
| `doc_version` | `raw_doc_asset.doc_version` | Optional. |
| `page_count` | `raw_doc_asset.page_count` | Optional. |
| `source_fingerprint` | `raw_doc_asset.source_fingerprint` | Stable version/fingerprint. |
| `pii_level` | `raw_doc_asset.pii_level::text` | Enum normalized to string. |
| `quality_gate` | `raw_doc_asset.quality_gate::text` | Enum normalized to string. |
| `ingest_ts` | `raw_doc_asset.ingest_ts` | Time field. |

## `silver.ticket_fact`

Source: `ticket_fact`. Arrays `error_codes` and `asset_ids` remain list fields in Arrow/Iceberg.

Write strategy: deterministic full refresh from current PostgreSQL Silver state.

## `silver.knowledge_doc`

Source: `knowledge_doc`. This is metadata-only in Week04. Section/chunk content remains Week07-08 scope.

Write strategy: deterministic full refresh from current PostgreSQL Silver document state.

## Field Gaps

- `raw_ticket_event.event_id` is not a natural id; Week04 does not use it for dedupe.
- `knowledge_doc.title` and richer document parsing fields may be sparse until parse/normalize weeks.
- Iceberg partitioning is intentionally minimal in Student Core Pack to keep local execution stable; partition evolution can be introduced later.

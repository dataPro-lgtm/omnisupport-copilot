# Week04 Lakehouse Foundation v1

## Goal

Week04 upgrades the Week03 ingest baseline into a reproducible Lakehouse state.
The minimum closed loop is:

1. PostgreSQL source tables hold Week03 ingest results.
2. PyIceberg loads a SQL Catalog backed by PostgreSQL.
3. MinIO stores Iceberg metadata and Parquet files under `s3://omni-lakehouse/warehouse`.
4. Four core tables are created and materialized:
   - `bronze.raw_ticket_event`
   - `bronze.raw_doc_asset`
   - `silver.ticket_fact`
   - `silver.knowledge_doc`
5. Metadata inspection, time travel, schema evolution, and baseline reports are runnable from devbox.

## Technology Choice

Chosen path: PyIceberg + PostgreSQL SQL Catalog + MinIO.

Reasons:
- It is Docker-only for students; no host Python, Spark, Trino, Hive, or Nessie setup is required.
- PostgreSQL already exists in Week01-03 and can back the SQL Catalog.
- MinIO already exists and is S3-compatible, so warehouse storage stays local and portable.
- PyIceberg directly exposes snapshots, history, schema evolution, and Arrow-based writes.

Explicit non-goals for Week04:
- No Spark.
- No Hive Metastore.
- No Nessie.
- No Trino.
- No REST catalog service.
- No dbt semantic layer or Gold mart implementation.
- No RAG/indexing migration to Iceberg.

## Runtime Boundary

The primary Week04 execution path is devbox:

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.catalog --smoke
```

Dagster remains a thin orchestration view in Week04. The compose Dagster service uses the upstream `dagster/dagster-k8s` image, so PyIceberg runtime dependencies are not assumed there. If the Dagster asset is materialized before the image is extended, it records that devbox is the primary path.

## Write Modes

| Table | Week04 write mode | Reason |
|---|---|---|
| `bronze.raw_ticket_event` | deduped full refresh | `event_id` is generated in PostgreSQL, so the source is deduped by `source_id + source_fingerprint` before writing. |
| `bronze.raw_doc_asset` | deterministic full refresh | `source_id` is already the stable asset key. |
| `silver.ticket_fact` | deterministic full refresh | This is a current-state table and must not blind append. |
| `silver.knowledge_doc` | deterministic full refresh | This is a current document state table and must not blind append. |

This is deliberately conservative for Student Core Pack. Append/merge maintenance can be introduced later when table growth justifies it.

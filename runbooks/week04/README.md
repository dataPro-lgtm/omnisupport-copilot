# Week04 Runbook: Lakehouse Minimum Closed Loop

## 0. Scope

Week04 turns Week03 ingest results into Iceberg-backed table state. It does not implement Week05 semantic models, Week07 parsing, Week08 RAG, or Week10 tools.

## 1. Start Required Services

```bash
cp infra/env/.env.example infra/env/.env.local
```

```bash
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build postgres minio minio_init
```

## 2. Validate Settings

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.settings --check
```

Expected: `ok: true`.

## 3. Smoke Test Catalog and Warehouse

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.catalog --smoke
```

Expected:
- `omni-lakehouse` bucket exists.
- `bronze` and `silver` namespaces exist.
- Four core Iceberg tables exist.

## 4. Dry Run Materialization

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.materialize --all-core --dry-run
```

This reads PostgreSQL source tables and reports row counts without writing Iceberg snapshots.

## 5. Materialize Core Tables

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.materialize --all-core --report-json reports/week04/materialization_report.json
```

Expected core tables:
- `bronze.raw_ticket_event`
- `bronze.raw_doc_asset`
- `silver.ticket_fact`
- `silver.knowledge_doc`

## 6. Inspect Metadata

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.inspect_metadata --table silver.ticket_fact --view snapshots
```

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.inspect_metadata --table silver.ticket_fact --view files
```

## 7. Time Travel Demo

For a stronger classroom demo, run materialization twice, then run:

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.demo_time_travel --table silver.ticket_fact --out reports/week04/time_travel_demo_report.md
```

## 8. Schema Evolution Demo

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.demo_schema_evolution --table bronze.raw_doc_asset --add-column source_checksum_algo --out reports/week04/schema_evolution_demo_report.md
```

Only additive columns are in scope.

## 9. Baseline Report

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.perf_baseline --all-core --out reports/week04/iceberg_baseline_report.md
```

Baseline records current table state. It is not a tuning benchmark and does not run compaction.

## 10. Tests

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/test_week4_iceberg_schema_contract.py -v
```

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/integration/test_week4_catalog_smoke.py tests/integration/test_week4_lakehouse_smoke.py tests/integration/test_week4_time_travel.py tests/integration/test_week4_perf_baseline.py -v
```

## 11. Troubleshooting

| Symptom | Check |
|---|---|
| `pyiceberg` import fails | Rebuild devbox with `docker compose --profile tools ... build devbox`. |
| MinIO bucket missing | Rerun `docker compose ... up -d minio minio_init`. |
| Catalog cannot connect | Confirm `ICEBERG_CATALOG_URI` points at `postgres:5432` inside compose. |
| Dagster asset skips | Expected unless Dagster image is extended; use devbox CLI as the primary path. |

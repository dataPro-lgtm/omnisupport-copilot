# Week04 Course Site Sync Packet v1

Use this packet when updating the separate Quarto course site. Do not copy commands that are not implemented in this repo.

## Real Repo Paths

- Runbook: `runbooks/week04/README.md`
- Existing architecture runbook: `runbooks/lakehouse_runbook.md`
- Code: `pipelines/lakehouse/`
- Settings: `pipelines/lakehouse/settings.py`
- Catalog smoke: `pipelines/lakehouse/catalog.py`
- Materialization: `pipelines/lakehouse/materialize.py`
- Metadata demo: `pipelines/lakehouse/inspect_metadata.py`
- Time travel demo: `pipelines/lakehouse/demo_time_travel.py`
- Schema evolution demo: `pipelines/lakehouse/demo_schema_evolution.py`
- Baseline report CLI: `pipelines/lakehouse/perf_baseline.py`

## Student Commands

```bash
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build postgres minio minio_init
```

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.catalog --smoke
```

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.materialize --all-core --dry-run
```

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.materialize --all-core --report-json reports/week04/materialization_report.json
```

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.inspect_metadata --table silver.ticket_fact --view snapshots
```

## Known Limits

- Dagster is a thin wrapper until the project owns a Dagster image with PyIceberg dependencies.
- Week04 does not introduce Spark, Trino, Hive, Nessie, dbt, or RAG serving over Iceberg.
- Sparse document fields are expected before parse/normalize weeks.

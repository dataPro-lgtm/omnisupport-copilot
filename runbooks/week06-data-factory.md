# Week06 Data Factory Runbook

Week06 focuses on assetized orchestration, dry-run backfill, checks, and run evidence. It does not replace the Week03 ingest logic, Week04 lakehouse CLI path, or Week05 dbt path.

## Scope

This runbook covers:

- Loading the Week06 Dagster definitions.
- Running the data factory asset graph for one daily partition.
- Generating a backfill dry-run plan.
- Running five asset checks.
- Writing schema-valid run evidence JSON and Markdown summaries.
- Verifying Docker Compose and Podman Compose compatibility.

## Prerequisites

```bash
cp infra/env/.env.example infra/env/.env.local

docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build postgres minio minio_init
```

For Podman, use the same env file and compose file:

```bash
podman compose --env-file infra/env/.env.local -f infra/docker-compose.yml config
podman compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build postgres minio minio_init
```

Do not run Docker and Podman stacks at the same time on one laptop; they use the same host ports.

## UI Path

Start the full stack:

```bash
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build
```

Open Dagster:

```text
http://localhost:3000
```

Look for the Week06 asset group:

```text
week06/source/seed_manifests
week06/factory/manifest_gate
week06/ingestion/raw_ticket_events_partitioned
week06/silver/ticket_fact_partitioned
week06/external/lakehouse_state
week06/external/support_kpi_mart
week06/ops/backfill_plan
week06/ops/run_evidence_report
week06/ops/data_factory_delivery_summary
```

Use partition `2026-04-17` for the default classroom demo.

## CLI Path

Validate the Week06 contract:

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/test_week06_run_evidence_schema.py -q
```

Validate Dagster definitions:

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/integration/test_week06_definitions_loadable.py -q
```

Materialize the Week06 asset graph in dry-run mode:

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/integration/test_week06_asset_graph_smoke.py -q
```

Generate a backfill dry-run plan:

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.data_factory.backfill_plan --partition 2026-04-17 --mode dry-run
```

Run checks and evidence tests:

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/integration/test_week06_asset_checks.py tests/integration/test_week06_run_evidence_generation.py -q
```

Podman uses the same commands with `podman compose`.

## Backfill / Replay Operation

Week06 supports dry-run backfill planning only. It does not execute destructive rewrites.

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.data_factory.backfill_plan --partition 2026-04-17 --mode dry-run
```

The report is written under:

```text
reports/week06/backfill/
```

The plan includes:

- partition window
- upstream manifest id
- expected source rows
- current output rows
- gap reason
- proposed action
- idempotency guard
- downstream impact

## Checks Acceptance

Week06 includes five Student Core checks:

| Check | Purpose |
|---|---|
| `manifest_consistency` | At least one structured manifest exists and has assets |
| `row_count_output_count` | Ingest wrapper saw non-zero valid rows |
| `duplicate_idempotency` | Seed tickets have no duplicate `ticket_id` |
| `required_field_null_rate` | Required fields are populated |
| `partition_completeness` | Selected partition has at least one source row |

Optional Week04/Week05 checks are observation-only. Missing optional evidence must be reported as `not_available`, not `passed`.

## Evidence Archive

Generated runtime files:

```text
reports/week06/backfill/*.json
reports/week06/checks/*.json
reports/week06/run_evidence/*.json
reports/week06/asset_checks_summary.md
reports/week06/run_evidence_summary.md
reports/week06/week06_delivery_summary.md
```

Runtime JSON/Markdown evidence is ignored by Git except for committed summary templates and course sync notes.

## Recovery Decision Tree

| Symptom | Decision |
|---|---|
| Contract schema test fails | Fix `contracts/run_evidence/week06_run_evidence.schema.json` or generated payload |
| Definitions fail to load | Check devbox has `dagster` installed and `pipelines/definitions.py` imports are valid |
| Dagster UI cannot see Week06 docs/contracts | Check compose mounts under `/workspace` |
| Backfill plan has zero expected input rows | Use a partition present in seed data, e.g. `2026-04-17` |
| Evidence says `dry_run_no_db_write` | Expected default; set `WEEK06_INGEST_DRY_RUN=false` only for instructor-controlled DB write demos |
| Week04 state is `not_available` | Run Week04 materialization first or keep it optional |
| Week05 state is `not_available` | Run Week05 dbt build first or keep it optional |

## Downstream Decision

Default classroom mode emits:

```text
downstream_decision=dry_run_only
```

Use `proceed_to_week07` only when:

- Week06 core checks pass.
- The structured ingest path is intentionally run outside dry-run mode.
- Evidence JSON validates against the Week06 schema.

## Known Limitations

- Week06 does not introduce Dagster+.
- Week06 does not run full dynamic partitions.
- Week06 does not rewrite historical data.
- Week06 does not make Week04/Week05 required dependencies.
- Week06 does not implement Week07 document parsing or Week08 retrieval.

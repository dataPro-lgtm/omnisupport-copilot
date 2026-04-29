# Week06 Data Factory Blueprint

Week06 turns the Week03-Week05 runnable paths into an asset-oriented data factory. The goal is not to rewrite ingest, lakehouse, or analytics logic. The goal is to provide orchestration boundaries, partitions, checks, backfill planning, and run evidence that can be inspected in Dagster and executed from the Docker or Podman devbox.

## Scope

Student Core Pack includes:

- Structured ticket source manifest discovery.
- Manifest admission gate for the structured domain.
- Daily partition wrapper around the existing Week03 ticket ingest dry-run path.
- Silver ticket fact delivery status derived from the same ingest result.
- Optional Week04 lakehouse state observation.
- Optional Week05 support KPI mart observation.
- Backfill dry-run plan generation.
- Five minimal asset checks.
- Run evidence JSON and Markdown summaries.

Out of scope:

- Rewriting `pipelines/ingestion/ticket_ingest.py`.
- Rewriting Week04 PyIceberg materialization.
- Rewriting Week05 dbt models or KPI tools.
- Implementing Week07 parsing, Week08 RAG, or Week10 HITL.

## Runtime Boundary

The primary execution path remains:

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox <command>
```

Podman uses the same compose file:

```bash
podman compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox <command>
```

Dagster UI is used for asset visibility and classroom lineage. The compose Dagster service must see:

- `/workspace/contracts` as read-only.
- `/workspace/docs` as read-only.
- `/workspace/runbooks` as read-only.
- `/workspace/analytics` as read-only.
- `/workspace/data` as read-only.
- `/workspace/reports` as writable.

## Evidence Policy

Week06 does not mark optional downstream dependencies as passed unless evidence exists.

If Week04 lakehouse evidence is absent, downstream evidence must use:

```json
{
  "status": "not_available",
  "reason_codes": ["week04_lakehouse_not_available"]
}
```

If Week05 analytics evidence is absent, downstream evidence must use:

```json
{
  "status": "not_available",
  "reason_codes": ["week05_analytics_not_available"]
}
```

If Week06 is running in default dry-run mode, DB writes are intentionally skipped and downstream decision remains `dry_run_only`.

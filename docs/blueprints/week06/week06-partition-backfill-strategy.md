# Week06 Partition and Backfill Strategy

Week06 uses daily partitions for the Student Core Pack. This is deliberately simple: one date maps to one source-window validation and one backfill dry-run plan.

## Partition Rules

- Partition granularity: day.
- Start date: `WEEK06_PARTITION_START_DATE`, default `2026-03-01`.
- Demo partition: `WEEK06_DEFAULT_PARTITION`, default `2026-04-17`.
- Partition field: ticket `created_at`.
- Timezone: UTC.

## Backfill Plan Fields

Each dry-run plan contains:

- `partition_key`
- `window_start`
- `window_end`
- `upstream_manifest_id`
- `expected_input_count`
- `current_output_count`
- `gap_reason`
- `proposed_action`
- `idempotency_guard`
- `downstream_impact`
- `operator`
- `timestamp`

## Safety Rules

- Default mode is `dry-run`.
- No real data is deleted to create a gap.
- No full table rerun is proposed unless the partition window is invalid.
- Current output count is observation-only unless a DB query path is explicitly enabled later.
- The proposed action is a plan, not execution.

## CLI

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.data_factory.backfill_plan --partition 2026-04-17 --mode dry-run
```

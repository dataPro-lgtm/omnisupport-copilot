# Week06 Run Evidence Spec

Run evidence is the audit artifact that connects a Dagster asset, a partition, checks, optional downstream state, and a downstream decision.

## Required Fields

The machine-readable contract is:

```text
contracts/run_evidence/week06_run_evidence.schema.json
```

Required fields:

- `evidence_schema_version`
- `run_id`
- `asset_key`
- `partition_key`
- `status`
- `started_at`
- `finished_at`
- `report_path`
- `reason_codes`

## Optional Fields

Optional fields include:

- `manifest_id`
- `batch_id`
- `input_row_count`
- `output_row_count`
- `source_snapshot_id`
- `output_snapshot_id`
- `dbt_invocation_id`
- `semantic_metric_count`
- `lakehouse_snapshot_id`
- `data_release_id`
- `trace_id`
- `git_sha`
- `downstream_decision`
- `checks`

## Status Semantics

| Status | Meaning |
|---|---|
| `success` | Core evidence exists and checks pass |
| `warning` | Core path is usable but a warning must be reviewed |
| `skipped` | Operator intentionally did not execute a step, commonly dry-run DB write |
| `not_available` | Optional downstream evidence is missing |
| `failed` | A required core check failed |

## Downstream Decision

| Decision | Meaning |
|---|---|
| `proceed_to_week07` | Structured data factory evidence is sufficient for Week07 handoff |
| `manual_review_required` | Core data is available but warnings require review |
| `hold_downstream` | Required checks failed |
| `dry_run_only` | Default class-safe mode; no persistent DB write has been performed |

# Week06 Asset Graph

Week06 asset keys are namespaced under `week06/` so they do not collide with existing Week01-Week05 assets.

```text
week06/source/seed_manifests
  -> week06/factory/manifest_gate
    -> week06/ingestion/raw_ticket_events_partitioned
      -> week06/silver/ticket_fact_partitioned
        -> week06/ops/run_evidence_report
          -> week06/ops/data_factory_delivery_summary

week06/external/lakehouse_state
  -> week06/ops/run_evidence_report

week06/external/support_kpi_mart
  -> week06/ops/run_evidence_report

week06/ops/backfill_plan
  -> week06/ops/run_evidence_report
```

## Core Assets

| Asset key | Role | Source of truth |
|---|---|---|
| `week06/source/seed_manifests` | Read source manifests | `data/seed_manifests/*.json` |
| `week06/factory/manifest_gate` | Select structured ticket manifest | `source_manifest_schema.json` + ticket manifest metadata |
| `week06/ingestion/raw_ticket_events_partitioned` | Wrap Week03 ticket ingest | `pipelines/ingestion/ticket_ingest.py` |
| `week06/silver/ticket_fact_partitioned` | Summarize structured delivery | Week03 ingest stats |
| `week06/external/lakehouse_state` | Observe Week04 state | `reports/week04/materialization_report.json` when present |
| `week06/external/support_kpi_mart` | Observe Week05 state | `analytics/target/run_results.json` when present |
| `week06/ops/backfill_plan` | Generate dry-run backfill plan | `pipelines/data_factory/backfill_plan.py` |
| `week06/ops/run_evidence_report` | Write schema-valid evidence JSON | `contracts/run_evidence/week06_run_evidence.schema.json` |
| `week06/ops/data_factory_delivery_summary` | Write classroom summary | `reports/week06/week06_delivery_summary.md` |

## Default Partition

The default classroom partition is `2026-04-17`, because the committed synthetic ticket seed contains records on that date. Operators can override the partition in Dagster or CLI commands.

# Week04 Performance Baseline Template

The generated report is not a benchmark. It records the current table shape so later weeks can compare deltas.

Minimum fields:
- row count
- snapshot count
- file count
- average file size
- min/max file size
- latest snapshot id
- latest operation

Command:

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.perf_baseline --all-core --out reports/week04/iceberg_baseline_report.md
```

Do not run compaction automatically in Week04.

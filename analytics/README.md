# Week05 Analytics Engineering

Week05 adds a local dbt Core project on PostgreSQL. It turns Week03/Week04 support data into governed marts and a read-only KPI surface for the Tool API.

Run from the devbox:

```bash
cd /workspace/analytics
DBT_PROFILES_DIR=. dbt debug
DBT_PROFILES_DIR=. dbt build --select tag:week05
DBT_PROFILES_DIR=. dbt docs generate
python scripts/validate_metric_registry.py
```

The Agent-facing path is intentionally not NL2SQL. It reads `support_kpi_mart` through a metric registry and contract-validated filters only.

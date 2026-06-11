# Week05 Analytics Engineering

Week05 adds a local dbt Core project on PostgreSQL. It turns Week03/Week04 support data into governed marts and a read-only KPI surface for the Tool API.

## Code Structure

This map shows the Week05 code path from PostgreSQL source tables to dbt layers, metric registry, and the governed Tool API query runtime.

![Week05 analytics code structure](../docs/assets/week05/analytics-code-structure.png)

Reading order:
- `models/sources.yml`
- `models/staging/`
- `models/intermediate/`
- `models/marts/`
- `metric_registry_v1.yml`
- `../services/tool_api/app/kpi_query.py`

## Run Commands

Run from the devbox:

```bash
cd /workspace/analytics
DBT_PROFILES_DIR=. dbt debug
DBT_PROFILES_DIR=. dbt build --select tag:week05
DBT_PROFILES_DIR=. dbt docs generate
python scripts/validate_metric_registry.py
```

The Agent-facing path is intentionally not NL2SQL. It reads `support_kpi_mart` through a metric registry and contract-validated filters only.

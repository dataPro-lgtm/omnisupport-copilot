# Week05 dbt Build Evidence

This file records the classroom validation commands for Week05. The commands below were run from the Docker `devbox` path on 2026-04-28.

| Check | Command | Status |
|---|---|---|
| dbt debug | `cd analytics && DBT_PROFILES_DIR=. dbt debug` | passed: all checks passed |
| dbt build | `cd analytics && DBT_PROFILES_DIR=. dbt build --select tag:week05` | passed: 37/37, `support_case_mart=50`, `support_kpi_mart=300` |
| dbt docs | `cd analytics && DBT_PROFILES_DIR=. dbt docs generate` | passed: catalog written to `analytics/target/catalog.json` |
| registry validator | `python analytics/scripts/validate_metric_registry.py --json` | passed: `valid=true`, `metric_count=6` |
| KPI query positive | `PYTHONPATH=services/tool_api python -m app.kpi_query --example valid` | passed: `allowed=true`, `row_count=16` |
| KPI query negative | `PYTHONPATH=services/tool_api python -m app.kpi_query --example bad_metric` | passed: `denial_code=METRIC_DENIED` |
| KPI query negative | `PYTHONPATH=services/tool_api python -m app.kpi_query --example bad_role` | passed: `denial_code=ROLE_DENIED` |
| Tool API endpoint | `POST /api/v1/tools/query_support_kpis` | passed: `allowed=true`, `row_count=5` |
| Full pytest | `pytest -q` | passed: 65 passed, 2 skipped |
| Ruff targeted | `ruff check analytics ... tests/integration/test_week05_kpi_query_tool.py` | passed |

Generated `analytics/target/` artifacts are local runtime outputs and are not committed.

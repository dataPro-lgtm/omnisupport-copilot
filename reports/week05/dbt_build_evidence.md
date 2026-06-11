# Week05 dbt Build Evidence

This file records the classroom validation commands for Week05. The commands below were run from the Docker `devbox` path on 2026-05-10 after the v1.1 experimental metric-pack extension.

| Check | Command | Status |
|---|---|---|
| dbt debug | `cd analytics && DBT_PROFILES_DIR=. dbt debug` | passed: all checks passed |
| dbt build | `cd analytics && DBT_PROFILES_DIR=. dbt build --select tag:week05` | passed: 39/39, `support_case_mart=50`, `support_kpi_mart=436` |
| dbt docs | `cd analytics && DBT_PROFILES_DIR=. dbt docs generate` | passed: catalog written to `analytics/target/catalog.json` |
| registry validator | `python analytics/scripts/validate_metric_registry.py --json` | passed: `valid=true`, `metric_count=11`, `experimental_metric_count=1` |
| KPI query positive | `PYTHONPATH=services/tool_api python -m app.kpi_query --example valid` | passed: `allowed=true`, `row_count=16`, `policy_applied` includes `parameterized_sql` |
| KPI query negative | `PYTHONPATH=services/tool_api python -m app.kpi_query --example bad_metric` | passed: `denial_code=METRIC_DENIED` |
| KPI query negative | `PYTHONPATH=services/tool_api python -m app.kpi_query --example bad_role` | passed: `denial_code=ROLE_DENIED` |
| KPI query negative | `PYTHONPATH=services/tool_api python -m app.kpi_query --example bad_experimental` | passed: `denial_code=EXPERIMENTAL_METRIC_NOT_ACKNOWLEDGED` |
| KPI query negative | `PYTHONPATH=services/tool_api python -m app.kpi_query --example bad_org_scope` | passed: `denial_code=ORG_SCOPE_REQUIRED` |
| Tool API endpoint | `POST /api/v1/tools/query_support_kpis` | passed: `allowed=true`, `row_count=5` |
| Week05 targeted pytest | `pytest tests/contract/test_week05_metric_contracts.py tests/integration/test_week05_metric_registry.py tests/integration/test_week05_kpi_query_tool.py -q` | passed: 11 passed |
| Regression subset | `pytest tests/contract/test_json_schemas.py tests/contract/test_week02_gate.py tests/contract/test_week05_metric_contracts.py tests/integration/test_ingest_state.py tests/integration/test_replay_backfill_dry_run.py tests/integration/test_week4_lakehouse_smoke.py tests/integration/test_week05_metric_registry.py tests/integration/test_week05_kpi_query_tool.py -q` | passed: 53 passed |

Generated `analytics/target/` artifacts are local runtime outputs and are not committed.

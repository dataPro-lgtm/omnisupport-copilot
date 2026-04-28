# Week05 Runbook — dbt KPI Mart + Governed KPI Tool

本 runbook 面向课堂实操。目标是本地跑通一条完整链路：PostgreSQL source -> dbt staging/intermediate/marts -> metric registry -> `query_support_kpis_v1` 工具调用。

## 0. 前置边界

- 本周不改 Week01-Week04 的主路径。
- 本周不要求宿主机安装 PostgreSQL、Python 或 dbt，默认走 Docker `devbox`。
- 本周不引入 dbt Cloud、MetricFlow、Snowflake、BigQuery、Spark 或 Trino。
- 本周不做 NL2SQL，Agent 只能通过白名单工具查询指标。

## 1. 启动依赖

```bash
cp infra/env/.env.example infra/env/.env.local

docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build postgres minio minio_init
```

如果本地已有 Week03/Week04 数据，可直接进入 dbt。否则先准备工单数据：

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python data/synthetic_generators/ticket_simulator.py --count 500 \
    --output data/canonization/tickets/tickets-seed-week05.jsonl

docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.ingestion.ticket_ingest \
    --input data/canonization/tickets/tickets-seed-week05.jsonl \
    --batch-id week05-demo
```

## 2. dbt debug

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  bash -lc 'cd analytics && DBT_PROFILES_DIR=. dbt debug'
```

课堂讲解点：
- `analytics/profiles.yml` 通过环境变量连接 Docker 网络内的 `postgres`。
- `analytics/models/sources.yml` 明确 dbt source，不让下游模型猜原表。

## 3. dbt build

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  bash -lc 'cd analytics && DBT_PROFILES_DIR=. dbt build --select tag:week05'
```

预期结果：
- `stg_*`、`int_*`、`support_case_mart`、`support_kpi_mart`、`agent_tool_input_view` 构建成功。
- dbt tests 全部通过。
- `no_pii_columns_in_agent_tool_input_view` 通过，说明工具视图没有暴露 PII/正文列。

## 4. 生成 dbt docs

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  bash -lc 'cd analytics && DBT_PROFILES_DIR=. dbt docs generate'
```

课堂讲解点：
- `target/catalog.json` 和 `target/manifest.json` 是 dbt 可观测和血缘说明的基础。
- 这些 target 产物是本地生成物，不提交到 main。

## 5. 校验 Metric Registry

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python analytics/scripts/validate_metric_registry.py --json
```

预期结果：
- `valid: true`
- 指标数大于等于 5
- safe view 字段包含 `metric_date`、`metric_name`、`metric_value` 和允许维度。

## 6. 调用受控 KPI 工具

正向调用：

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  bash -lc 'PYTHONPATH=services/tool_api python -m app.kpi_query --example valid'
```

负向调用，未知指标被拒绝：

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  bash -lc 'PYTHONPATH=services/tool_api python -m app.kpi_query --example bad_metric || true'
```

负向调用，角色无权限被拒绝：

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  bash -lc 'PYTHONPATH=services/tool_api python -m app.kpi_query --example bad_role || true'
```

课堂讲解点：
- 返回 `allowed=true` 才代表工具调用被允许。
- 返回 `allowed=false` 时要看 `denial_code`，例如 `METRIC_DENIED`、`ROLE_DENIED`。
- 工具运行时只查 `analytics.agent_tool_input_view`，不查原始表，不接收 raw SQL。

## 7. Tool API 端点验证

```bash
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build tool_api

curl -s http://localhost:8001/health

curl -s -X POST http://localhost:8001/api/v1/tools/query_support_kpis \
  -H 'Content-Type: application/json' \
  -H 'X-Actor-ID: instructor-local' \
  -d '{
    "actor_role": "instructor",
    "metrics": ["ticket_count"],
    "date_from": "2026-04-01",
    "date_to": "2026-04-30",
    "dimensions": ["product_line", "priority"],
    "limit": 20
  }'
```

## 8. 回归检查

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/test_json_schemas.py tests/contract/test_week02_gate.py tests/contract/test_week05_metric_contracts.py -q

docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/integration/test_ingest_state.py tests/integration/test_replay_backfill_dry_run.py tests/integration/test_week4_lakehouse_smoke.py tests/integration/test_week05_metric_registry.py tests/integration/test_week05_kpi_query_tool.py -q
```

通过标准：
- Week01/Week02 contract gate 不退化。
- Week03 ingest state/replay/backfill dry-run 不退化。
- Week04 lakehouse dry-run 不退化。
- Week05 registry 和 KPI 工具测试通过。

## 9. 不提交的本地产物

- `analytics/target/`
- `analytics/logs/`
- `analytics/dbt_packages/`
- Week03/Week04/Week05 本地实验生成的临时 JSON、截图和 target artifacts，除非文档明确要求作为课程交付证据。

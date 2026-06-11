# Week05 Metric Registry Contract v1

`analytics/metric_registry_v1.yml` 是 Week05 的语义控制面。它把 dbt mart 中的可查询字段显式登记出来，避免 Agent 直接猜表名、猜字段或生成 SQL。

## Registry 字段

| 字段 | 作用 |
|---|---|
| `registry_id` | 审计和版本识别 |
| `source_model` | 指标来源 mart，当前为 `support_kpi_mart` |
| `safe_view` | 工具运行时唯一可查询视图，当前为 `agent_tool_input_view` |
| `time_dimension` | 时间过滤字段，当前为 `metric_date` |
| `measure_column` | 数值字段，当前为 `metric_value` |
| `max_window_days` | 单次查询最大时间窗口，防止大范围扫描 |
| `allowed_dimensions` | 允许返回的维度 |
| `allowed_filters` | 允许过滤的字段 |
| `allowed_roles` | 允许调用 registry 的角色 |
| `metrics` | 指标定义和指标级角色白名单 |

## v1.1 Metric Metadata

Week05 v1.1 要求每个 metric 额外声明：

| 字段 | 作用 |
|---|---|
| `business_name_zh` | 中文业务名，用于课堂和业务沟通 |
| `business_definition_zh` | 中文口径说明 |
| `owner` | 指标 owner，出问题时有人负责 |
| `metric_type` | `count`、`average` 或 `ratio` |
| `formula` | 人类可读公式 |
| `unit` | 指标单位，例如 `tickets`、`minutes`、`ratio` |
| `sensitivity` | `low`、`medium`、`high` |
| `definition_status` | `production` 或 `experimental_proxy` |
| `version` | 指标版本 |
| `quality_tests` | 对应质量规则 |

`ratio` 指标还必须声明 `numerator` 和 `denominator`。`experimental_proxy` 指标必须由 Tool Runtime 要求调用方显式确认，不能静默进入生产口径。

## 当前指标

| 指标 | 口径 |
|---|---|
| `ticket_count` | 选定窗口内创建的工单数 |
| `open_ticket_count` | mart 构建时仍处于打开状态的工单数 |
| `p1_ticket_count` | P1 级别工单数 |
| `sla_breach_count` | SLA 超期工单数 |
| `escalation_count` | 升级状态工单数 |
| `avg_backlog_age_days` | 平均 case age |
| `avg_first_response_minutes` | 平均首响分钟数 |
| `avg_handle_time_minutes` | 平均处理分钟数 |
| `first_resolution_rate` | 一次解决率实验代理口径 |
| `escalation_rate` | 升级率 |
| `sla_breach_rate` | SLA 违约率 |

## 校验命令

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python analytics/scripts/validate_metric_registry.py --json
```

通过标准：`valid=true`，`metric_count>=5`，且所有维度/过滤器都属于 safe view 字段集合。

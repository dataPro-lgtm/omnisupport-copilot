# Replay / Backfill Strategy v1

## 目标

把 Week03 课上常讲的四类恢复动作，在 repo 中变成可运行的计划对象，并支持显式执行 ticket ingest 补数。

## 四类动作

| Mode | Meaning | Week03 repo state |
|------|---------|-------------------|
| `retry` | 同一逻辑运行再试一次 | plan 支持；`--execute --input` 可执行 |
| `rerun` | 按当前声明再跑一次完整 ingest | plan 支持；`--execute --input` 可执行 |
| `replay` | 对历史已知 batch 重新处理 | plan 支持；`--execute --input` 可执行 |
| `backfill` | 对历史 cursor / time window 做补跑 | plan 支持；`--execute --input` 可执行 |

## repo 落点

- 计划/执行入口：`pipelines/ingestion/replay_backfill.py`
- 真实写入执行器：`pipelines/ingestion/ticket_ingest.py`
- 状态输入：`data/canonization/checkpoints/week03_ingest_state.json`
- 决策输出：`reports/week03/recovery_decision_log.json`

## 决策输入

- `mode`
- `source_id`
- `batch_id`
- `start_cursor`
- `end_cursor`
- checkpoint snapshot

## 默认只做什么

- 输出结构化计划
- 输出 warnings
- 输出推荐动作
- 不直接改 DB，除非显式传入 `--execute`
- 不直接改对象存储

## 显式执行边界

`replay_backfill.py --execute --input <ticket-jsonl>` 会调用 `ticket_ingest`。执行时仍受两层保护：

- `raw_ticket_event` 使用 `source_id + source_fingerprint` 幂等键，重跑同一原始记录不会新增重复 Bronze 行。
- `ticket_ingest` 成功后写入 checkpoint，`checkpoint_snapshot` 会随 state 文件变化。

## Week04 / Week06 如何继续消费

- Week04 可以把 decision log 纳入 release / audit 体系
- Week06 可以把 plan / execute 两段式封装成 Dagster recovery task

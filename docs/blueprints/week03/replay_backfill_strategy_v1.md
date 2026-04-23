# Replay / Backfill Strategy v1

## 目标

把 Week03 课上常讲的四类恢复动作，在 repo 中变成可运行的 dry-run 对象。

## 四类动作

| Mode | Meaning | Week03 repo state |
|------|---------|-------------------|
| `retry` | 同一逻辑运行再试一次 | dry-run 规划已支持 |
| `rerun` | 按当前声明再跑一次完整 ingest | dry-run 规划已支持 |
| `replay` | 对历史已知 batch 重新处理 | dry-run 规划已支持 |
| `backfill` | 对历史 cursor / time window 做补跑 | dry-run 规划已支持 |

## repo 落点

- 执行器：`pipelines/ingestion/replay_backfill.py`
- 状态输入：`data/canonization/checkpoints/week03_ingest_state.json`
- 决策输出：`reports/week03/recovery_decision_log.json`

## 决策输入

- `mode`
- `source_id`
- `batch_id`
- `start_cursor`
- `end_cursor`
- checkpoint snapshot

## Week03 只做什么

- 输出结构化计划
- 输出 warnings
- 输出推荐动作
- 不直接改 DB
- 不直接改对象存储

## Week04 / Week06 如何继续消费

- Week04 可以把 decision log 纳入 release / audit 体系
- Week06 可以把 dry-run 计划升级成实际 recovery task

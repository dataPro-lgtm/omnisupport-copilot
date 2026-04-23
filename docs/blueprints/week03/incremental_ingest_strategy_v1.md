# Incremental Ingest Strategy v1

## 目标

让 `load_mode` 和 checkpoint/state 在 repo 中形成最小对应，而不是只停留在讲义概念层。

## 当前 repo 已有基础

- `source_manifest_schema.json` 已支持：
  - `full_snapshot`
  - `incremental_cursor`
  - `cdc`
  - `replay`
  - `backfill`
- `seed_loader.py` 已校验不同 `load_mode` 对 `selection_window` 的要求

## Week03 最小策略

### full_snapshot

- 适用于：Week01 / Week02 baseline manifest
- 状态要求：可无 checkpoint
- 风险：容易覆盖处理边界

### incremental_cursor

- 适用于：`manifest_week02_practice_v1.json`
- 最小字段：
  - `selection_window.cursor_field`
  - `selection_window.cursor_start`
- Week03 新增：
  - `last_processed_cursor`

### replay

- 适用于：重放某次已知 batch
- 最小字段：
  - `selection_window.replay_from_batch`
  - 或 state 中的 `last_success_batch_id`

### backfill

- 适用于：补历史窗口
- 最小字段：
  - `selection_window.start_at`
  - `selection_window.end_at`

## 状态对象如何承接

状态文件字段：

- `source_id`
- `last_processed_cursor`
- `last_success_batch_id`
- `last_run_id`
- `updated_at`

它不是完整 state service，只是 Week03 的最小落点。

## 当前 repo 的现实约束

- state 目前还是 JSON file，不是 DB state table
- `ticket_ingest.py` / `doc_ingest.py` 还未自动更新 checkpoint
- Week03 只要求“看得见、能测、可 dry-run 规划”

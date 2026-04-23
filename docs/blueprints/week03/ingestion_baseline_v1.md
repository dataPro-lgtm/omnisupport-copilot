# Week03 Ingestion Baseline v1

## 目标

在不破坏 Week01 / Week02 基线的前提下，把 repo 的 ingestion 能力推进到 Week03 可讲、可测、可继续扩展的状态。

## 边界

- 继续复用 `seed_loader.py`、`ticket_ingest.py`、`doc_ingest.py`
- 不引入 Kafka / Debezium / Flink
- 不重写 Dagster 编排结构
- Student Core Pack 继续保持 Docker + CLI 可跑

## 当前 repo 已有能力

- `contracts/data/*.json`：单条对象 contract
- `data/seed_manifests/*.json`：批次声明
- `pipelines/ingestion/seed_loader.py`：manifest admission gate
- `pipelines/ingestion/ticket_ingest.py`：ticket Bronze/Silver 写入
- `pipelines/ingestion/doc_ingest.py`：document Bronze/Silver 写入
- `infra/migrations/001_init.sql`：PostgreSQL 表定义

## Week03 最小新增能力

1. 最小 checkpoint/state 对象
2. smoke summary 报告落盘
3. replay/backfill dry-run 决策脚手架
4. Week03 blueprint / runbook
5. integration tests

## 当前还没有 fully automated 的部分

- `seed_loader.py` 仍然是 dry-run/admission gate，不直接做真实写入
- `ticket_ingest.py` 和 manifest admission 仍是两段式
- `doc_ingest.py` 真实 ingest 只覆盖 document 侧
- replay/backfill 目前只有 planning，不是自动执行器

## 最小实现落点

- 状态对象：`pipelines/ingestion/ingest_state.py`
- 状态文件：`data/canonization/checkpoints/week03_ingest_state.json`
- 恢复 dry-run：`pipelines/ingestion/replay_backfill.py`
- 报告目录：`reports/week03/*.json`

## 验证方法

1. `pytest tests/contract -v`
2. `pytest tests/integration -v`
3. `python -m pipelines.ingestion.seed_loader ... --report-json reports/week03/seed_loader_smoke_report.json`
4. `python -m pipelines.ingestion.ticket_ingest ... --dry-run --report-json reports/week03/ticket_ingest_smoke_report.json`
5. `python -m pipelines.ingestion.doc_ingest ... --dry-run --report-json reports/week03/doc_ingest_smoke_report.json`
6. `python -m pipelines.ingestion.replay_backfill --mode replay --source-id ... --dry-run`

## Week04 / Week06 如何继续消费

- Week04 可以直接消费 smoke reports 作为 batch evidence
- Week04 可以用 state 文件承接 time-travel / replay 决策
- Week06 可以把 `replay_backfill.py` 的 dry-run plan 升级成真正的 orchestrated recovery job

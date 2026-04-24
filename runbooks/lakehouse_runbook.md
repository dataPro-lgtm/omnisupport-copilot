# Runbook: Week04 Lakehouse Baseline

> 适用范围：Week04 Iceberg / Snapshot / Time Travel 最小工程讲解

## 目标

用 Week03 已经接好的 ingest 结果，解释 Week04 为什么要把数据推进到可复现、可回滚、可追溯的 Lakehouse 层。

## Architecture Map

![Week04 Lakehouse 详细架构图](../docs/assets/week04/lakehouse-detailed-architecture.png)

建议先用这张图讲 5 分钟，再进入代码文件。讲解顺序按图从左到右：
- 上游交接层：Week03 的 `ticket_ingest.py` / `doc_ingest.py` 如何把结构化和文档资产交给 Week04
- Week04 代码与编排层：`pipelines/lakehouse/assets.py`、`pipelines/lakehouse/iceberg_schemas.py`、`pipelines/definitions.py`
- Catalog / Warehouse 运行时层：PostgreSQL SQL Catalog、MinIO Warehouse、Dagster orchestration
- Bronze Iceberg 层：保真落盘，不做过早业务解释
- Silver Iceberg 层：形成 `ticket_current`、`knowledge_doc` 这类可查询、可演化的规范化表
- Snapshot / Time Travel / Baseline：让“本次数据长什么样”变成可验证、可比较、可回滚的状态

课堂上可以先用一句话把 Week04 定住：
- Week04 交付的不是“多几张表”，而是让 Week03 的 ingest 结果进入可复现、可回滚、可作为下游基座的数据底座。

## Files to Open

- `pipelines/ingestion/ticket_ingest.py`
- `pipelines/ingestion/doc_ingest.py`
- `pipelines/lakehouse/assets.py`
- `pipelines/lakehouse/iceberg_schemas.py`
- `pipelines/definitions.py`
- `docs/blueprints/project-blueprint.md`

## Demo Steps

1. 先从 `ticket_ingest.py` 和 `doc_ingest.py` 出发，强调 Week03 交付的是 ingest 入口，不是最终 Lakehouse。
2. 打开 `pipelines/lakehouse/assets.py`，说明 Bronze / Silver / Gold 资产在 Dagster 里的注册关系。
3. 打开 `pipelines/lakehouse/iceberg_schemas.py`，解释 Bronze 和 Silver 在 schema 设计上的差异：
   - Bronze：保真、append-first、少做业务解释
   - Silver：curated、可查询、可演化、为 Week05 语义层做准备
4. 打开 `pipelines/definitions.py`，说明 ingest、parse、lakehouse 三层资产如何被统一注册。
5. 再回到架构图，讲 `snapshot / time travel / rollback` 为什么不是运维附属功能，而是数据工程主链路的一部分。

## What to Emphasize

- Week03 解决的是“怎么可靠接进来”，Week04 解决的是“接进来之后怎么形成可信数据底座”。
- Iceberg 的价值不只是表格式存储，而是 `snapshot`、`time travel`、`schema evolution` 和可追溯版本。
- Bronze 和 Silver 不是重复造表，而是刻意把“原始保真”和“服务消费”拆开。
- Week05 的 `dbt / models / semantic metrics` 会直接建立在 Week04 的 Silver 基座之上。

## 当前仓库状态

- `pipelines/lakehouse/assets.py` 已有 Week04 的资产骨架和说明
- `pipelines/lakehouse/iceberg_schemas.py` 已定义 Bronze / Silver / Gold 目标形态
- 当前还没有完整的 PyIceberg materialization demo、time travel 脚本和 Week04 专属测试
- 所以这份 runbook 现阶段更适合做“代码级讲解入口”，后续再接 Week04 的真实执行命令

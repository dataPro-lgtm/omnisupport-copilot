# Batch Ingestion Design v1

## 目标

把当前 repo 中“按批处理 ingest”的关键对象和责任边界固定下来。

## 批处理最小对象

### 1. Source Manifest

文件：
- `data/seed_manifests/source_manifest_schema.json`
- `data/seed_manifests/manifest_*.json`

责任：
- 声明 batch 边界
- 绑定 `contract_ref`
- 声明 `load_mode`
- 指定 `selection_window`
- 指定 `gate_policy`

### 2. Admission Result

文件：
- `pipelines/ingestion/seed_loader.py`

责任：
- 先校验 manifest
- 再按 asset 输出 `accept / warn / quarantine / reject`

### 3. Execution Result

文件：
- `pipelines/ingestion/ticket_ingest.py`
- `pipelines/ingestion/doc_ingest.py`

责任：
- 产生真实 ingest summary
- 输出 `batch_id`
- 生成 smoke report
- 工单 raw Bronze 使用 `source_id + source_fingerprint` 幂等写入

### 4. Checkpoint State

文件：
- `pipelines/ingestion/ingest_state.py`
- `data/canonization/checkpoints/week03_ingest_state.json`

责任：
- 记录 source 上次成功处理到哪里
- 为 replay/backfill 决策提供输入
- `ticket_ingest.py` 在非 dry-run 且无 invalid/error 时自动更新

## Batch 粒度下的核心字段

| Field | Why |
|------|-----|
| `manifest_id` | 唯一标识一份运行声明 |
| `batch_id` | 唯一标识一次 ingest 批次 |
| `contract_ref` | 绑定数据对象约束 |
| `load_mode` | 声明批次处理语义 |
| `selection_window` | 声明时间窗 / cursor / replay 范围 |
| `last_success_batch_id` | 连接 batch history 和 recovery |

## 当前 repo 的实现边界

- 批次声明已经存在
- 批次 admission 已经存在
- 文档 / 工单的执行器已经存在
- batch checkpoint 由 `ticket_ingest.py` 自动写入
- replay/backfill 默认输出 plan；显式 `--execute --input` 才执行补数

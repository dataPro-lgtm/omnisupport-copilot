# Week02 Metadata Minimums v1

> 适用范围：Week02 课时 3 | 当前 repo 的第一版输入标准
> 说明：课程大纲里会把 Data Contract 写成 YAML 概念对象；当前 OmniSupport Copilot 仓库在 Week02 第一版统一落到 JSON Schema 和 JSON manifest。这里先定义最小 metadata 基线，再由 `contracts/data/*.json` 承接为可执行 gate。

## 1. Week02 统一原则

1. metadata 不是备注，而是后续检索、引用、权限和审计要消费的 runtime interface。
2. 先定义 source-level minimum，再在 Week03/Week07 把 page/utterance/frame 级字段落到 parse 结果。
3. 高风险字段不能只标记“有 PII”，还必须能映射到动作：`allow` / `mask` / `redact` / `block` / `human_review`。
4. 当前 repo 的 Week02 contract 先覆盖输入资产对象，不强行在这一周把所有 parse-stage 字段都塞进 raw asset contract。

## 2. Shared Core Fields

这些字段应被四类输入共同遵守；如果缺失，后续 contract、manifest、RAG、审计都会变得不稳。

| Field | Why it exists | Current repo surface |
|------|---------------|----------------------|
| `source_id` | 全局唯一标识；连接 inventory、manifest、contract、run evidence | `contracts/data/*`, `data/seed_manifests/*.json` |
| `schema_version` | 区分对象版本，避免静默漂移 | `contracts/data/*` |
| `ingest_batch_id` | 把内容绑定到一次具体 ingest | `contracts/data/*` |
| `product_line` | 让路由、权限、评测和 demo 叙事保持一致 | ticket/audio/video/doc contract |
| `owner` | 没有 owner 的输入无法形成责任闭环 | ticket/audio/video/doc contract |
| `license_tag` | 决定能不能分发、能不能进训练/索引、需不需要隔离 | doc/audio/video contract, manifest |
| `pii_level` | 决定后续默认动作，不是简单标签 | 四类 contract |
| `quality_gate` | 把输入是否够格进入系统显式化 | 四类 contract |
| `source_fingerprint` or raw path | 后续证明“这条内容到底来自哪里”的最小抓手 | doc contract, raw object paths |
| `ingest_ts` / `created_at` / `updated_at` | 支撑增量窗口、回放、审计定位 | contracts + manifest selection window |

## 3. Modality Minimums

### 3.1 Ticket

| Field | Required in Week02 | Why |
|------|---------------------|-----|
| `ticket_id` | Yes | 工单主键，不允许靠 subject 近似识别 |
| `status` | Yes | 影响 KPI、分流、工具动作，是最容易静默漂移的字段 |
| `priority` | Yes | 决定 SLA 与 HITL 边界 |
| `customer_id` / `org_id` | `customer_id` required, `org_id` recommended | 没有租户上下文就无法做 entitlement 和越权隔离 |
| `created_at` / `updated_at` | `created_at` required | Week03 的 incremental cursor 直接依赖这些时间字段 |
| `pii_redacted` | Recommended, valid record should carry it | 让“已扫描”和“已脱敏”分开，不把 high PII 默认视作可放行 |

### 3.2 Document

| Field | Required in Week02 | Why |
|------|---------------------|-----|
| `source_url` | Yes | 后续 citation、回链、审计都要用 |
| `source_fingerprint` | Yes | 文档被重抓或重传时，fingerprint 才能识别内容变化 |
| `doc_version` | Recommended | release notes / manual 更新时避免静默混版本 |
| `page_count` | Recommended | 为 parse completeness 提供基线 |
| `raw_object_path` | Recommended | Week03 raw zone / MinIO 的入口 |

Parse-stage hard fields to preserve next:

- `page_no`
- `section_path`
- `bbox`
- `heading_path`

说明：这些字段会在文档被 parse/chunk 后进入 `knowledge_section` 或后续 evidence anchor；Week02 先在标准里声明，Week03/Week07 再在 pipeline 里落具体记录。

### 3.3 Audio

| Field | Required in Week02 | Why |
|------|---------------------|-----|
| `call_id` | Yes | 音频资产必须能回到原始会话 |
| `duration_sec` | Yes | 判断是否完整、是否异常截断 |
| `transcript_object_path` | Recommended | 没有 transcript path，后面无法接 utterance-level pipeline |
| `speaker_count` / `diarization_available` | Recommended | 直接影响 speaker_role 是否可用 |
| `asr_confidence` | Recommended | 让质量风险在输入层暴露，而不是等回答坏了才发现 |

Parse-stage hard fields to preserve next:

- `start_ts`
- `end_ts`
- `speaker_role`
- `utterance_id`

### 3.4 Video

| Field | Required in Week02 | Why |
|------|---------------------|-----|
| `video_id` | Yes | 视频资产的唯一主键 |
| `duration_sec` | Yes | 判断切片、OCR、字幕覆盖率是否合理 |
| `transcript_object_path` | Recommended | 视频问答最终还是要落到 transcript + frame evidence |
| `keyframes_prefix` | Recommended | 后续 OCR / frame evidence 的入口 |
| `segment_count` | Recommended | 让 chunk / segment 的完整性可验证 |

Parse-stage hard fields to preserve next:

- `frame_ts`
- `segment_id`
- `ocr_text`
- `frame_bbox`

## 4. Teaching Mapping: Course Site vs Current Repo

| Course emphasis | Current repo Week02 landing | Why this split is intentional |
|----------------|-----------------------------|-------------------------------|
| `page_no / section_path / bbox` | 先写进 metadata 标准与 runbook，不直接要求 raw doc asset 全量携带 | 这些字段要在 parse/chunk 之后才稳定出现 |
| `speaker_role / start_ts / end_ts` | 先写进 audio metadata standard 与 fixture 说明 | 说话人粒度字段属于 transcript segment，不应伪造到 raw call asset |
| 字段级 PII 动作矩阵 | `pii_policy_matrix_v1.csv` + manifest gate policy | 先把动作定清，再决定 contract 和 loader 如何消费 |
| YAML contract | 当前 repo 用 JSON Schema + JSON manifest 实现 machine-readable gate | 课程方法论保留，工程落地使用 repo 现有栈，避免重复维护两套格式 |

## 5. Minimum Definition of Ready

一条输入对象要进入 Week03 ingest baseline，至少满足下面三条：

1. 它已经在 `asset_inventory_v1.csv` 里被明确归类为 `ready_now` 或 `conditional`。
2. 它的 modality minimum fields 已经能映射到对应 contract。
3. 它的高风险 PII 字段，已经能在 `pii_policy_matrix_v1.csv` 里找到默认动作。

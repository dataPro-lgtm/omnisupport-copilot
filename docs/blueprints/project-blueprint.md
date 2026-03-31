# OmniSupport Copilot — 项目蓝图 v1.0

> 文档定位：工程基线蓝图 | 适用阶段：贯穿 Week01–Week15
> 最后更新：2026-03-31 | 版本：v1.0

---

## 1. 一句话定义

OmniSupport Copilot 是一个面向企业支持场景的**准生产级多模态 AI 系统**：
支持文档问答、证据引用、工单查询/创建/更新、指标查询、人工介入、审计追踪、回归评测、版本与回滚。

---

## 2. 业务世界观

### 虚构企业：Northstar Systems

| 产品线 | 定位 | 典型数据 |
|--------|------|---------|
| **Northstar Workspace** | 企业协作 / 工单 / 自动化 SaaS | Help Center, FAQ, Release Notes, API 文档, 工单, 权限, SLA |
| **Northstar Edge Gateway** | 边缘采集设备 / 网关类硬件 | PDF 安装手册, 规格说明, 接线图, 故障排查视频, 固件升级说明 |
| **Northstar Studio** | 实施与工作流监控产品 | 教学视频, 录屏教程, 集成文档, 错误码手册, 社区问答 |

### 核心业务对象

- **Customer / Org**：客户与组织，关联 SLA tier
- **Ticket**：工单，含状态、优先级、类别、错误码、资产关联
- **KnowledgeAsset**：文档/音频/视频资产，含版本、模态、证据链
- **Entitlement**：订阅与权限，控制工具调用边界
- **EvidenceAnchor**：证据锚点，连接生成答案与知识源

---

## 3. 系统架构（七层）

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 7: Observability / Governance                                │
│  OTel Collector → Phoenix │ OpenLineage │ lakeFS │ Release Manifest │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 6: Agent / Tool Layer                                        │
│  search_knowledge │ get_ticket_status │ create_ticket               │
│  update_ticket │ query_kpi │ escalate_to_human │ get_allowed_actions │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 5: Serving / Retrieval Layer                                 │
│  PostgreSQL + pgvector (学生基线) │ Postgres FTS │ Cross-Encoder    │
│  FastAPI RAG API (带 citations / trace_id / release_id)            │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 4: Lakehouse Curated Layer (Apache Iceberg)                  │
│  Bronze: raw_* │ Silver: *_fact/*_dim/knowledge_* │ Gold: *_mart    │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3: Parse / Normalize Layer                                   │
│  Docling/Unstructured (文档) │ Whisper (ASR) │ FFmpeg (视频切片)    │
│  OCR │ Image Verbalization │ PII 脱敏 │ Metadata 统一               │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 2: Landing / Raw Zone                                        │
│  MinIO (S3 兼容) │ 按 modality+source+date 分桶                    │
│  source_fingerprint │ ingest_batch_id │ license_tag                 │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 1: Source Layer                                              │
│  Structured: ticket/customer/entitlement/SLA/product               │
│  Semi-structured: webhook/JSON config/audit log                    │
│  Unstructured: PDF/HTML/FAQ/Release Notes/Community                │
│  Audio: 客服通话/TTS合成/语音备注                                   │
│  Video: 教学视频/安装录屏/支持演示                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| 对象存储 | MinIO (S3 兼容) | 本地可跑，与 S3 接口统一 |
| 湖仓 | Apache Iceberg + PyIceberg | 快照/时间旅行/Schema Evolution |
| 编排 | Dagster | 资产化定义，回填与血缘内置 |
| 结构化 + 向量 | PostgreSQL + pgvector | 单服务覆盖 FTS + 向量，学生本地可跑 |
| 服务层 | FastAPI | 轻量，契约测试友好 |
| 文档解析 | Docling / Unstructured | 结构保真，表格/图像/坐标保留 |
| ASR | Whisper (OpenAI) | 本地可跑，多语言支持 |
| LLM | Anthropic Claude API | 课程主模型 |
| 可观测 | OpenTelemetry + Phoenix | AI 请求级 tracing |
| 血缘 | OpenLineage | dataset/job/run 追踪 |
| 数据版本 | lakeFS | Git for data，分支/合并/回滚 |

---

## 5. 数据模型概览

### Bronze（保真落盘）
- `raw_ticket_event` — 工单原始事件流
- `raw_doc_asset` — 文档原始资产记录
- `raw_audio_asset` — 音频原始记录
- `raw_video_asset` — 视频原始记录
- `raw_transcript_segment` — 转写片段

### Silver（规范化）
- `ticket_fact` / `ticket_comment_fact`
- `customer_dim` / `entitlement_dim` / `asset_dim`
- `knowledge_doc` / `knowledge_section`
- `media_segment` / `transcript_segment`
- `evidence_anchor` / `source_manifest`

### Gold（服务消费）
- `support_case_mart` / `support_kpi_mart`
- `kb_serving_asset` / `entitlement_serving_view`
- `product_issue_taxonomy` / `agent_tool_input_view`

---

## 6. 核心接口契约

### RAG 响应结构
```json
{
  "answer": "string",
  "citations": ["string"],
  "evidence_ids": ["string"],
  "confidence": 0.0,
  "release_id": "string",
  "trace_id": "string"
}
```

### 工具调用必需字段
每个工具必须包含：`name`, `json_schema`, `allowed_roles`, `idempotency_key`, `audit_fields`, `failure_codes`, `hitl_conditions`

---

## 7. 逐周实现计划

| Week | 阶段 | 主要产出 |
|------|------|---------|
| W01 | Phase 0: Foundation | 工程骨架, contracts, seed manifest, 蓝图文档 |
| W02-03 | Phase 1: Contracts & Ingest | 四类数据契约, seed loader, ticket+doc ingest |
| W04 | Phase 2: Lakehouse | Iceberg Bronze/Silver, time travel demo |
| W05 | Phase 2 | KPI mart, tool-safe semantic layer |
| W06 | Phase 2 | Dagster 资产化, backfill, lineage |
| W07 | Phase 2 | 多模态 parse pipeline, 证据链 |
| W08 | Phase 2 | 混合检索 + 重排 + RAG API |
| W09-10 | Phase 3: Tools | Skill Pack, 工单工具, HITL, 审计 |
| W11 | Phase 3 | 多模态 eval set + regression gate |
| W12 | Phase 3 | OTel/Phoenix tracing, bad case replay |
| W13 | Phase 3 | GraphRAG (issue-symptom-resolution graph) |
| W14 | Phase 3 | lakeFS + OpenLineage + release manifest |
| W15 | Phase 3 | 成本/SLO/Runbook/Capstone 交付包 |

---

## 8. 实施原则

1. **Data-first**：先做数据层、边界、契约，再做生成层
2. **Workflow-first**：先做稳定工作流，再引入复杂 Agent
3. **Evidence-first**：所有回答必须带 `evidence_anchor` / `citation`
4. **Release-aware**：所有服务预埋 `release_id`, `trace_id`, `eval_run_id`
5. **Dual-scale**：Student Core Pack（本地可跑）+ Instructor Scale Pack（规模演示）

---

## 9. Week01 交付物清单

- [x] `infra/docker-compose.yml` — 9 服务基线 Compose
- [x] `contracts/data/` — 4 类数据契约 JSON Schema
- [x] `contracts/tools/` — 工具契约规范 + 3 个具体工具定义
- [x] `contracts/release/` — Release Manifest Schema + 示例
- [x] `data/seed_manifests/` — 3 份种子清单
- [x] `docs/blueprints/project-blueprint.md` — 本文档
- [x] `docs/blueprints/boundary-checklist.md` — 风险边界清单
- [ ] `services/rag_api/` — FastAPI RAG 服务骨架
- [ ] `services/tool_api/` — FastAPI Tool 服务骨架
- [ ] `pipelines/` — Dagster pipeline 骨架
- [ ] `pyproject.toml` + 基础测试 + smoke test

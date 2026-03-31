# OmniSupport Copilot

多模态企业支持知识层 + 工单联动 AI 系统（准生产级课程项目）

---

## 一句话定义

面向虚构企业 **Northstar Systems** 的准生产级多模态 AI 支持系统：
支持文档问答、证据引用、工单查询/创建/更新、指标查询、人工介入（HITL）、审计追踪、回归评测、版本与回滚。

---

## 快速启动（Week01 基线）

```bash
# 1. 复制环境变量
cp infra/env/.env.example infra/env/.env.local
# 填写 ANTHROPIC_API_KEY

# 2. 启动所有服务
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d

# 3. 验证健康
curl http://localhost:8000/health   # RAG API
curl http://localhost:8001/health   # Tool API
open http://localhost:3000          # Dagster UI
open http://localhost:9001          # MinIO Console
open http://localhost:6006          # Phoenix (AI 可观测)

# 4. 生成种子工单数据
python data/synthetic_generators/ticket_simulator.py --count 500 \
    --output data/canonization/tickets/tickets-seed-001.jsonl

# 5. 运行契约测试
pip install -e ".[dev]"
pytest tests/contract/ -v
```

---

## 业务世界观

| 产品线 | 定位 | 典型数据 |
|--------|------|---------|
| **Northstar Workspace** | 企业协作 / 工单 / 自动化 SaaS | Help Center, FAQ, Release Notes, API 文档, 工单 |
| **Northstar Edge Gateway** | 边缘采集设备 / 网关硬件 | PDF 安装手册, 规格说明, 接线图, 故障排查视频 |
| **Northstar Studio** | 实施与监控产品 | 教学视频, 录屏教程, 错误码手册, 社区问答 |

---

## 架构总览（七层）

```
Source → Raw Zone (MinIO) → Parse/Normalize → Lakehouse (Iceberg)
→ Serving (pgvector) → Agent/Tool (FastAPI) → Observability (OTel/Phoenix)
```

详见 [docs/blueprints/project-blueprint.md](docs/blueprints/project-blueprint.md)

---

## 仓库结构

```
omnisupport-copilot/
├── infra/                      # Docker Compose + 数据库 migrations + 环境变量
├── services/
│   ├── rag_api/                # FastAPI RAG 检索生成服务 (port 8000)
│   └── tool_api/               # FastAPI 工单工具 + HITL + 审计 (port 8001)
├── pipelines/                  # Dagster 资产化 pipeline
│   ├── ingestion/              # Seed loader + 采集资产
│   ├── parse_normalize/        # 文档解析 + 切片 + 证据链
│   ├── lakehouse/              # Iceberg Bronze/Silver/Gold 表
│   └── indexing/               # 向量索引构建
├── contracts/                  # JSON Schema 数据/工具/发布契约
│   ├── data/                   # 四类数据契约 (doc/ticket/audio/video)
│   ├── tools/                  # 工具契约规范 + 具体工具定义
│   └── release/                # Release Manifest Schema
├── data/
│   ├── seed_manifests/         # 种子数据清单
│   ├── synthetic_generators/   # 合成工单/音频生成器
│   └── canonization/           # 规范化后的课程资产
├── observability/              # OTel Collector 配置 + Phoenix + dashboards
├── evals/                      # 评测集 + eval harness + 回归报告
├── tests/
│   ├── contract/               # JSON Schema 契约测试
│   ├── integration/            # API smoke tests
│   └── eval_regression/        # 回归评测测试
├── docs/blueprints/            # 项目蓝图 + 风险边界清单
└── runbooks/                   # 运维操作手册
```

---

## 逐周进度

| Week | 状态 | 主要产出 |
|------|------|---------|
| W01 | ✅ | 工程基线、契约、seed manifest、蓝图 |
| W02-03 | 🔄 | 四类数据契约、ingest pipeline |
| W04 | 📅 | Iceberg Bronze/Silver、time travel |
| W05-08 | 📅 | KPI mart、多模态解析、混合检索、RAG API |
| W09-15 | 📅 | Tool层、评测、Tracing、GraphRAG、治理、Capstone |

---

## 核心实施原则

1. **Data-first** — 先数据层，再生成层
2. **Workflow-first** — 先稳定工作流，再复杂 Agent
3. **Evidence-first** — 所有回答必须带 `evidence_anchor` / `citation`
4. **Release-aware** — 所有服务预埋 `release_id`, `trace_id`
5. **Dual-scale** — Student Core Pack（本地可跑）+ Instructor Scale Pack（规模演示）

---

## 非功能性要求

- **可重复**：同 release 组合离线评测可复现
- **可观测**：所有请求携带 `trace_id`，关键 span 可查
- **可回滚**：30 分钟内可回滚到上一稳定 release
- **可审计**：高风险操作记录完整审计日志

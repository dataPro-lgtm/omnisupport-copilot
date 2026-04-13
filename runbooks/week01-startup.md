# Runbook: Week01 工程基线启动手册

> 适用范围：Week01 初始化 | 执行者：讲师/学员
> 版本：v1.0 | 最后更新：2026-03-31

---

## 前置条件

- Docker Desktop / Docker Engine 已安装（≥ 24.0）
- Docker Compose V2（`docker compose` 命令可用）
- `ANTHROPIC_API_KEY` 可选（Week01 留空可先验证工程基线）

> Week01 推荐走 **Docker-only** 路线：不要求学员本地先配置 Python 依赖。
> 默认 compose 不把 PostgreSQL 暴露到宿主机，避免与本机数据库冲突。

---

## 步骤 1：克隆仓库并配置环境

```bash
cd /path/to/workspace
# 复制环境变量模板
cp infra/env/.env.example infra/env/.env.local

# 编辑 .env.local，如需真实 LLM 调用再填写:
# ANTHROPIC_API_KEY=sk-ant-...
# （其余字段保持默认即可）
```

---

## 步骤 2：启动所有服务

```bash
docker compose --env-file infra/env/.env.local \
               -f infra/docker-compose.yml \
               up -d --build
```

预期状态：`postgres / minio / rag_api / tool_api / dagster / otel_collector / phoenix` 为 `Up`，
`minio_init` 为一次性初始化成功后退出。

---

## 步骤 3：验证各服务健康

```bash
# RAG API
curl -s http://localhost:8000/health

# Tool API
curl -s http://localhost:8001/health

# MinIO (浏览器打开控制台)
# http://localhost:9001
# 用户名: minioadmin / 密码: minioadmin
# 确认 8 个 bucket 已创建

# Dagster UI
# http://localhost:3000

# Phoenix (AI 可观测)
# http://localhost:6006
```

---

## 步骤 4：生成种子工单数据（无本地依赖）

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python data/synthetic_generators/ticket_simulator.py \
  --count 500 \
  --output data/canonization/tickets/tickets-seed-001.jsonl
```

---

## 步骤 5：dry-run seed loader（验证 manifest 校验，无本地依赖）

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.ingestion.seed_loader \
  --manifest-dir data/seed_manifests
```

预期输出：显示 3 个 manifest，无 REJECTED 条目，成功率 100%。

---

## 步骤 6：运行契约测试（无本地依赖）

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/ -v
```

**Week01 DoD**：所有契约测试必须通过（绿色）。

---

## 步骤 7：冒烟测试 RAG API

```bash
# 发送一个测试查询
curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "如何配置 Northstar Workspace SSO？"}'

# 确认响应包含以下字段:
# answer, citations, evidence_ids, confidence, release_id, trace_id
```

---

## 步骤 8：验证 Release Manifest

```bash
curl -s http://localhost:8000/api/v1/admin/release
# 预期: release_id = "dev-local"（或你在 .env.local 中自定义的 RELEASE_ID）
```

---

## 常见问题

| 问题 | 可能原因 | 处理方法 |
|------|---------|---------|
| minio_init 退出非 0 | MinIO 还未就绪 | 等待 30s 后重试 `docker compose restart minio_init` |
| rag_api health 返回 `database: down` | DB 未完成初始化 | 等待 `001_init.sql` 执行完成 |
| `docker compose run devbox ...` 失败 | 首次构建 devbox 镜像 | 先执行 `docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml build devbox` |
| contract tests 失败 | Schema 文件缺失 | 检查 `contracts/` 目录结构 |

---

## 停止与清理

```bash
# 停止所有服务（保留数据卷）
docker compose -f infra/docker-compose.yml down

# 完全清理（删除数据卷，重新开始）
docker compose -f infra/docker-compose.yml down -v
```

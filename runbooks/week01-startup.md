# Runbook: Week01 工程基线启动手册

> 适用范围：Week01 初始化 | 执行者：讲师/学员
> 版本：v1.0 | 最后更新：2026-03-31

---

## 前置条件

- Docker Desktop / Docker Engine 已安装（≥ 24.0）
- Docker Compose V2（`docker compose` 命令可用）
- Python 3.11+（本地运行测试用）
- `ANTHROPIC_API_KEY` 已申请

---

## 步骤 1：克隆仓库并配置环境

```bash
cd /path/to/workspace
# 复制环境变量模板
cp infra/env/.env.example infra/env/.env.local

# 编辑 .env.local，填写以下必填项:
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

预期输出：9 个容器全部 `Started` 或 `Healthy`。

---

## 步骤 3：验证各服务健康

```bash
# RAG API
curl -s http://localhost:8000/health | python3 -m json.tool

# Tool API
curl -s http://localhost:8001/health | python3 -m json.tool

# MinIO (访问控制台)
open http://localhost:9001
# 用户名: minioadmin / 密码: minioadmin
# 确认 8 个 bucket 已创建

# Dagster UI
open http://localhost:3000

# Phoenix (AI 可观测)
open http://localhost:6006
```

---

## 步骤 4：生成种子工单数据

```bash
# 生成 500 条合成工单
python data/synthetic_generators/ticket_simulator.py \
    --count 500 \
    --output data/canonization/tickets/tickets-seed-001.jsonl

# 确认生成成功
wc -l data/canonization/tickets/tickets-seed-001.jsonl
# 预期输出: 500
```

---

## 步骤 5：dry-run seed loader（验证 manifest 校验）

```bash
python -m pipelines.ingestion.seed_loader \
    --manifest-dir data/seed_manifests
```

预期输出：显示 3 个 manifest，无 REJECTED 条目，成功率 100%。

---

## 步骤 6：运行契约测试

```bash
pip install -e ".[dev]"
pytest tests/contract/ -v
```

**Week01 DoD**：所有契约测试必须通过（绿色）。

---

## 步骤 7：冒烟测试 RAG API

```bash
# 发送一个测试查询
curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "如何配置 Northstar Workspace SSO？"}' \
  | python3 -m json.tool

# 确认响应包含以下字段:
# answer, citations, evidence_ids, confidence, release_id, trace_id
```

---

## 步骤 8：验证 Release Manifest

```bash
curl -s http://localhost:8000/api/v1/admin/release | python3 -m json.tool
# 预期: release_id = "dev-20260331-001"
```

---

## 常见问题

| 问题 | 可能原因 | 处理方法 |
|------|---------|---------|
| postgres 容器不健康 | 端口 5432 被占用 | `lsof -i :5432`，停止冲突进程 |
| minio_init 退出非 0 | MinIO 还未就绪 | 等待 30s 后重试 `docker compose restart minio_init` |
| rag_api health 返回 `database: down` | DB 未完成初始化 | 等待 `001_init.sql` 执行完成 |
| contract tests 失败 | Schema 文件缺失 | 检查 `contracts/` 目录结构 |

---

## 停止与清理

```bash
# 停止所有服务（保留数据卷）
docker compose -f infra/docker-compose.yml down

# 完全清理（删除数据卷，重新开始）
docker compose -f infra/docker-compose.yml down -v
```

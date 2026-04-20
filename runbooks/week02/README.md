# Runbooks: Week02

> 用途：逐课时演示索引

## Lesson Map

1. [课时1：输入风险定位](./lesson1-input-risk.md)
2. [课时2：资产盘点与输入地图](./lesson2-asset-inventory.md)
3. [课时3：最小 metadata 与 PII](./lesson3-metadata-pii.md)
4. [课时4：Data Contract gate](./lesson4-contract-gate.md)
5. [课时5：Manifest 与 ingest admission](./lesson5-manifest-gate.md)

## Shared Preconditions

- 已存在 `infra/env/.env.local`
- Docker Desktop / Docker Engine 可用
- 在 repo 根目录执行命令

## Shared Validation Commands

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/ -v
```

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.ingestion.seed_loader \
    --manifest-dir data/seed_manifests \
    --report-json docs/blueprints/week02/run_reports/week02-dry-run-report.json
```

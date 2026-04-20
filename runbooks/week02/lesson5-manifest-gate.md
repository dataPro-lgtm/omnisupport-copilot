# Week02 Lesson 5 Runbook

## Goal

让 contract 真正开始驱动 ingest admission，并生成最小 run evidence。

## Files to Open

- `data/seed_manifests/source_manifest_schema.json`
- `data/seed_manifests/manifest_week02_practice_v1.json`
- `pipelines/ingestion/seed_loader.py`
- `docs/blueprints/week02/ingest_strategy_v1.md`

## Demo Steps

1. 在 manifest schema 里解释 `contract_ref / load_mode / selection_window / gate_policy` 的语义。
2. 打开 practice manifest，指出三条 asset 分别为什么会变成 `accept / warn / quarantine`。
3. 打开 `seed_loader.py`，只讲三件事：
   - manifest validator
   - gate judgment ranking
   - report JSON
4. 执行：

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.ingestion.seed_loader \
    --manifest-dir data/seed_manifests \
    --report-json docs/blueprints/week02/run_reports/week02-dry-run-report.json
```

## What to Emphasize

- contract 回答“什么数据算合格”。
- manifest 回答“这次到底接哪一批”。
- gate 回答“现在能不能放行”。
- report JSON 回答“以后怎么追这次决定”。

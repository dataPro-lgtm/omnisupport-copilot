# Week02 Submission Readme

> 用途：作业提交说明 / 讲师审阅顺序 / 本地演示索引

## 1. Submission Tree

- `docs/blueprints/week02/asset_inventory_v1.csv`
- `docs/blueprints/week02/metadata_minimums_v1.md`
- `docs/blueprints/week02/pii_policy_matrix_v1.csv`
- `docs/blueprints/week02/ingest_strategy_v1.md`
- `docs/blueprints/week02/lab_report_v1.md`
- `contracts/data/ticket_contract.json`
- `contracts/data/doc_asset_contract.json`
- `contracts/data/audio_asset_contract.json`
- `contracts/data/video_asset_contract.json`
- `data/seed_manifests/manifest_week02_practice_v1.json`
- `tests/contract/fixtures/week02/sample_records.json`

## 2. Reviewer Order

1. 先看 `asset_inventory_v1.csv`，确认输入地图不是目录罗列。
2. 再看 `metadata_minimums_v1.md` 和 `pii_policy_matrix_v1.csv`，确认 metadata/PII 是否真能进入 runtime。
3. 再看四类 JSON contract，确认当前 repo 的 contract 是否覆盖 Week02 最小门禁。
4. 最后看 `manifest_week02_practice_v1.json` 与 dry-run 结果，确认 Week03 ingest 起跑线已经清楚。

## 3. Validation Commands

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

## 4. What This Package Proves

- Week02 不再只是概念讲义，而是已经落成 repo 中可执行的输入准入包。
- contract 与 manifest 已经通过当前 JSON Schema / JSON manifest 体系接起来。
- run evidence 已经能区分 `accept / warn / quarantine / reject`。
- Week03 可以直接消费 `load_mode`、`selection_window`、`contract_ref`。

## 5. Known Deliberate Boundaries

1. 课程大纲里的 YAML contract，在当前 repo v1 里故意收口为 JSON Schema，避免并行维护两套格式。
2. `page_no / bbox / speaker_role / frame_ts` 这类 parse-stage 字段，在 Week02 先写进 metadata 标准，不强行塞进 raw asset contract。
3. `audio` / `video` 当前以标准、fixture、runbook 为主；更完整的真实 ingest 会在 Week03/Week07 继续扩展。

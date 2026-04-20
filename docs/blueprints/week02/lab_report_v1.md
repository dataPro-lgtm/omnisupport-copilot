# Week02 Lab Report v1

> 对应页面：Week02 实验｜四类数据契约与输入门禁最小闭环
> 目标：把 Week02 的关键工件真正串成 `inventory -> metadata/PII -> contract -> manifest -> dry-run`

## 1. Lab Scope

- Repo: `omnisupport-copilot`
- 运行方式：Docker-first
- 重点验证：
  - 四类 JSON contract 是否可读、可测、可解释
  - `manifest_week02_practice_v1.json` 是否能表达 incremental ingest intent
  - `seed_loader` 是否能给出 `accept / warn / quarantine / reject` judgment

## 2. Files Reviewed

- `docs/blueprints/week02/asset_inventory_v1.csv`
- `docs/blueprints/week02/metadata_minimums_v1.md`
- `docs/blueprints/week02/pii_policy_matrix_v1.csv`
- `contracts/data/*.json`
- `data/seed_manifests/*.json`
- `tests/contract/fixtures/week02/sample_records.json`

## 3. Expected Validation Commands

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

## 4. What Counts as a Pass

1. `sample_records.json` 中四条 valid 记录都能通过当前 contract。
2. 至少一条 invalid 记录能在 contract validation 里被拦住。
3. `manifest_week02_practice_v1.json` 能通过 manifest schema。
4. practice manifest 的三条 asset 分别演示：
   - `accept`
   - `warn`
   - `quarantine`

## 5. Current Interpretation

| Source | Current judgment | Why |
|--------|------------------|-----|
| `structured:tickets:practice_ok` | `accept` | cursor 窗口、checksum、metadata、PII scan 都完整 |
| `structured:tickets:practice_warn` | `warn` | metadata 只有 partial，且 checksum 缺失 |
| `structured:tickets:practice_quarantine` | `quarantine` | PII scan 尚未执行，不应进入 Week03 ingest |

## 6. Compatibility Notes

- additive: `ticket.tags` 增加可选标签，不影响现有消费方。
- conditional: `audio.asr_confidence` 从可选变成门禁字段前，需要先补历史数据。
- breaking: `ticket.status` 的枚举语义变化，必须视作 breaking，而不是普通 schema 编辑。

## 7. Next Action Before Week03

1. 继续为 `audio` 和 `video` 补真实的 practice manifest。
2. 在 Week03 的 ingest state 里消费 `load_mode` 与 `selection_window`。
3. 让 `run_reports/week02-dry-run-report.json` 成为 replay / backfill 的起点证据。

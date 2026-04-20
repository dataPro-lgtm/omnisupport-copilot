# Week02 Lesson 4 Runbook

## Goal

把 Data Contract 从“字段清单”讲成“可执行 gate”。

## Files to Open

- `contracts/data/ticket_contract.json`
- `contracts/data/doc_asset_contract.json`
- `tests/contract/fixtures/week02/sample_records.json`
- `tests/contract/test_week02_gate.py`

## Demo Steps

1. 先讲 ticket contract：为什么 `status` 的语义变化是 breaking change。
2. 再讲 doc contract：为什么 `source_fingerprint / source_url` 是证据链入口。
3. 打开 `test_week02_gate.py`，说明 valid / invalid fixture 如何把 contract 变成 executable gate。
4. 执行：

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/ -v
```

## What to Emphasize

- additive: 新增可选字段。
- conditional: schema 不坏，但历史数据要不要补齐。
- breaking: shape 看起来还能解析，但语义承诺已经被打破。

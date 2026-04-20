# Week02 Lesson 1 Runbook

## Goal

建立一个判断：企业 AI 系统最危险的不是彻底报错，而是输入已经漂了但系统还在继续“正常回答”。

## Files to Open

- `README.md`
- `contracts/data/ticket_contract.json`
- `contracts/data/doc_asset_contract.json`
- `data/seed_manifests/manifest_tickets_synthetic_v1.json`

## Demo Steps

1. 打开 `ticket_contract.json`，指出 `status / priority / pii_level / quality_gate` 为什么是输入 gate，而不只是字段定义。
2. 打开 `doc_asset_contract.json`，说明 `source_fingerprint / source_url / license_tag` 为什么决定证据链与版权边界。
3. 打开 `manifest_tickets_synthetic_v1.json`，说明 contract 之外还需要 batch / load intent。
4. 执行：

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/ -v
```

## What to Emphasize

- 课时1不解决“怎么建索引”，只解决“为什么要先守住输入底线”。
- 学员此时应该能把输入风险收成三条线：事实、证据、边界。

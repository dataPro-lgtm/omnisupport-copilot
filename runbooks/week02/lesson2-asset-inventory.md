# Week02 Lesson 2 Runbook

## Goal

把“资源目录”升级成能直接进入后续 contract / manifest / ingest 的输入地图。

## Files to Open

- `docs/blueprints/week02/asset_inventory_v1.csv`
- `data/seed_manifests/manifest_workspace_helpcenter_v1.json`
- `data/seed_manifests/manifest_edge_gateway_pdf_v1.json`

## Demo Steps

1. 先解释 CSV 列头：`owner / access_boundary / evidence_granularity / onboarding_decision / contract_ref / load_mode`。
2. 对比 5 条记录里的 `ready_now / conditional / hold`。
3. 强调：`audio:studio:support_calls` 和 `video:edge:install_demos` 不是“没数据”，而是输入条件尚未满足。

## What to Emphasize

- 盘点的目的不是列资源，而是给系统做准入判断。
- `onboarding_decision` 必须能被后续 contract 与 ingest 继续消费。

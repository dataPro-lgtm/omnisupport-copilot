# Week02 Lesson 3 Runbook

## Goal

让学员理解 metadata 是 runtime interface，PII 是字段 × 动作矩阵，而不是简单标签。

## Files to Open

- `docs/blueprints/week02/metadata_minimums_v1.md`
- `docs/blueprints/week02/pii_policy_matrix_v1.csv`
- `tests/contract/fixtures/week02/sample_records.json`

## Demo Steps

1. 在 `metadata_minimums_v1.md` 里先讲 shared core fields。
2. 再讲 document / audio / video 的 parse-stage hard fields 为什么在 Week02 先声明、Week03/Week07 再落 pipeline。
3. 打开 `pii_policy_matrix_v1.csv`，重点看 `ticket.description`、`audio.pii_redacted`、`raw_object_path` 的默认动作。
4. 打开 `sample_records.json`，指出 valid 与 invalid 样例分别在为课时4做什么准备。

## What to Emphasize

- `page_no / bbox / speaker_role / frame_ts` 不是“好看字段”，而是后续 evidence anchor 的前提。
- 课程大纲里说 YAML，但本 repo Week02 的实际 gate 统一收口到 JSON Schema + JSON manifest。

# Week02 Teaching Gap Check

> 用途：把课程站 Week02、项目实施规格书、教学大纲，与当前 repo 的真实落点逐课时对齐

## 结论先行

Week02 的主线已经能在当前 repo 中闭环演示：

- 课时1：输入风险与三条底线
- 课时2：asset inventory 与 onboarding decision
- 课时3：metadata minimums 与 PII 动作矩阵
- 课时4：四类 JSON contract + fixture + contract tests
- 课时5：manifest + gate policy + dry-run + run evidence

但有两个边界需要讲清：

1. 教学大纲写的是 YAML contract；当前 repo 第一版统一收口为 JSON Schema / JSON manifest。
2. `page_no / bbox / speaker_role / frame_ts` 等 parse-stage 字段，Week02 先写标准，不在 raw asset contract 里伪造，等 Week03/Week07 pipeline 产出。

## 逐课时核对

| 课时 | 课程站核心要求 | 当前 repo 对应点 | 本次补齐内容 | 仍留到后续周次 |
|------|----------------|------------------|--------------|----------------|
| 课时1 | 让学员先建立“输入先坏”的判断 | `contracts/data/*.json`, `data/seed_manifests/*.json` | `runbooks/week02/lesson1-input-risk.md` | 无 |
| 课时2 | 从资源目录升级成输入地图 | `docs/blueprints/week02/asset_inventory_v1.csv` | 首版 inventory 已补齐，含 `ready_now / conditional / hold` | 更多真实 source 访谈与扩表 |
| 课时3 | 定义多模态最小 metadata 与字段级 PII 动作 | `metadata_minimums_v1.md`, `pii_policy_matrix_v1.csv`, `sample_records.json` | 已落地并解释 current repo 边界 | parse-stage 真实字段产出 |
| 课时4 | 把 contract 做成 machine-readable gate | 四类 JSON contract + `tests/contract/test_week02_gate.py` | 正反样例、practice manifest 校验、兼容性说明 | 更系统的 compatibility CLI / release policy |
| 课时5 | manifest 驱动 ingest admission | `source_manifest_schema.json`, `manifest_week02_practice_v1.json`, `seed_loader.py` | `contract_ref / load_mode / gate_policy / report-json` 已落地 | Week03 state / replay / backfill 真正写入链路 |

## 与教学大纲的差异处理

### 1. YAML vs JSON

教学大纲中的表述：

- “将 Schema、业务口径、质量门禁（SLA）固化为机器可读的 YAML 契约”

当前 repo 的 Week02 实际落地：

- `contracts/data/*.json`
- `data/seed_manifests/*.json`

为什么保留这个差异：

1. 当前 repo 已经存在 JSON Schema 契约体系。
2. 继续再造一套 YAML 只会增加维护成本，并不会让 gate 更可执行。
3. 课程里真正要讲的是 contract thinking，不是某种文件扩展名。

### 2. parse-stage metadata 为什么暂不硬塞 raw contract

课程站明确强调：

- document: `page_no / section_path / bbox`
- audio: `speaker_role / start_ts / end_ts`
- video: `frame_ts`

当前 repo 的处理：

- 这些字段已经写进 `metadata_minimums_v1.md`
- 但不强行塞进 `doc_asset_contract.json` / `audio_asset_contract.json` / `video_asset_contract.json`

原因：

1. 它们属于 parse 或 segment/frame 粒度，而不是 raw asset 粒度。
2. Week02 讲边界时，应该教“在哪里声明、什么时候真正产出”，而不是伪造字段。
3. 这样更利于 Week03/Week07 自然衔接 parse pipeline。

## 本次补齐后的最小教学闭环

1. 打开 `asset_inventory_v1.csv` 讲输入地图。
2. 打开 `metadata_minimums_v1.md` 和 `pii_policy_matrix_v1.csv` 讲输入标准。
3. 打开 `sample_records.json` 和 `test_week02_gate.py` 讲 contract gate。
4. 打开 `manifest_week02_practice_v1.json` 和 `seed_loader.py` 讲 manifest + gate policy。
5. 跑 `pytest tests/contract -q` 与 `python -m pipelines.ingestion.seed_loader ... --report-json ...` 收口。

## 当前完成度判断

| 维度 | 状态 | 说明 |
|------|------|------|
| 逐课时可讲 | ✅ | 五课时都有对应 runbook 和 repo 路径 |
| 逐课时代码可演示 | ✅ | contract tests 与 dry-run 已可运行 |
| 作业/实验可交付 | ✅ | blueprint pack、practice manifest、submission readme 已具备 |
| Docker 演示环境即时可跑 | ⚠️ | 命令已准备好，但本机当前 Docker daemon 未启动 |
| Week03 真实 ingest state | ⏭️ | 刻意留到下一周实现 |

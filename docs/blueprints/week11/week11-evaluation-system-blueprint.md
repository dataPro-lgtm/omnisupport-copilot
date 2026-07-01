# Week11 Evaluation System Blueprint

Week11 builds the quality control plane after Week10 controlled actions.

```text
Week08 RAG response / Week10 action output
  -> evals/sets/rag_qa_golden_v2_3_0.jsonl
  -> evals/week11/runner.py
  -> evals/week11/metrics.py
  -> eval report JSON
  -> evals/week11/regression.py
  -> release manifest / CI gate / business SLO
```

## File-Level Map

```text
contracts/evals/
  ├── eval_dataset.schema.json       # 每条 golden-set 样本的契约
  └── eval_report.schema.json        # runner 输出报告的契约

evals/sets/
  └── rag_qa_golden_v2_3_0.jsonl     # Week11 golden set，覆盖 4 类样本

evals/fixtures/week11/
  └── rag_predictions_good.jsonl     # 离线课堂 fixture，替代真实 RAG API 响应

evals/week11/
  ├── dataset.py                     # 加载、校验、digest、manifest
  ├── metrics.py                     # RAGAS 风格 6 指标 + safety pass
  ├── runner.py                      # predictions 或 /rag/answer 两种运行路径
  ├── regression.py                  # max-drop / min / no-drop 回归门禁
  ├── calibrate.py                   # Cohen kappa / Pearson / MAE / Top-K overlap
  ├── ab_test.py                     # 样本量估算 + A/B 近似检验
  └── business_slo.py                # 技术指标到业务 SLO 的 pass/fail

evals/
  ├── run_ragas.py                   # 课堂主入口
  ├── check_regression.py            # CI 门禁入口
  ├── calibrate.py                   # judge 校准入口
  └── ab_test.py                     # A/B 决策入口

contracts/release/
  ├── release_manifest_schema.json   # 绑定 eval_dataset / judge_calibration / business_slo
  └── release_manifest_example.json

.github/workflows/rag-eval-gate.yml  # PR Gate 示例
```

## Design Decisions

### 1. Deterministic first, LLM judge later

The classroom runner does not require RAGAS, DeepEval, or an online LLM judge.
It computes deterministic proxy metrics with the same report shape:

- `context_precision`
- `context_recall`
- `faithfulness`
- `answer_relevance`
- `answer_correctness`
- `semantic_similarity`

This keeps Docker/Podman classroom runs stable. Production can replace
`evals/week11/metrics.py` with real RAGAS / LLM-as-Judge while preserving
`contracts/evals/eval_report.schema.json`.

### 2. Dataset is a release asset

`evals/sets/rag_qa_golden_v2_3_0.jsonl` is not a loose test file. It carries:

- category: `happy / boundary / adversarial / multi_hop`
- expected answer
- expected keywords
- expected evidence IDs
- source document
- document version
- per-case thresholds

The release manifest binds the dataset by `id / version / digest`.

### 3. Red-team cases are stricter

Adversarial samples can pass by refusing, not by answering. `should_abstain`
and `forbidden_phrases` make the safety behavior explicit.

Regression gate uses:

```text
--no-drop adversarial_pass_rate
--no-drop safety_pass_rate
```

That means safety regressions block the release even if average quality looks
fine.

### 4. Judge prompt is versioned, not trusted blindly

`evals/judges/faithfulness.j2` and `evals/calibration/human_judge_gold_v1.jsonl`
show the production pattern:

1. Write judge prompt with scoring anchors.
2. Compare judge scores against human gold labels.
3. Record `cohen_kappa`, `pearson_r`, `mae`, and `top_k_overlap`.
4. Bind judge calibration summary into release manifest.

### 5. Business SLO is part of release quality

Week11 extends `contracts/release/release_manifest_schema.json` with:

- `eval_dataset`
- `judge_calibration`
- `business_slo`
- `rollout.auto_rollback_on`

This is the bridge to later governance weeks.

## Classroom Scope Boundary

Student Core Pack includes:

- JSONL golden set and schema.
- Deterministic local evaluation runner.
- Regression gate CLI.
- Judge prompt and calibration math.
- A/B helper.
- Business SLO checker.
- CI gate example.

Not included in Week11 Student Core:

- Mandatory online RAGAS execution.
- Mandatory paid LLM judge.
- Hosted evaluation dashboard.
- Full canary rollout controller.

Those are production expansions after students understand the control loop.


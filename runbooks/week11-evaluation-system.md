# Week11 Evaluation System Runbook

Week11 把 Copilot 质量从“感觉还行”变成可量化、可门禁、可监管的工程指标。

本周主线：

- Dataset：评测集是资产，不是一次性测试用例。
- Metrics：用 RAGAS 风格的 6 维指标拆开检索层、生成层、整体层。
- Judge：LLM-as-Judge 必须有 prompt、校准和 cross-evaluate 预留点。
- Gate：评测结果要能 block PR，不只是生成报告。
- Biz：把技术指标翻译成业务 SLO 和合规红线。

## 1. Inspect Week11 Files

```bash
find evals contracts/evals tests -maxdepth 3 -type f | sort | grep -E 'week11|eval_|rag_qa|baseline|judge|calibration|regression|ab_test'
```

重点文件：

- `evals/sets/rag_qa_golden_v2_3_0.jsonl`
- `evals/fixtures/week11/rag_predictions_good.jsonl`
- `evals/week11/metrics.py`
- `evals/week11/runner.py`
- `evals/week11/regression.py`
- `evals/week11/calibrate.py`
- `evals/week11/ab_test.py`
- `contracts/evals/eval_dataset.schema.json`
- `contracts/evals/eval_report.schema.json`
- `.github/workflows/rag-eval-gate.yml`

## 2. Validate Contracts

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/test_week11_eval_contracts.py -v
```

Expected:

- golden set 每条样本符合 `contracts/evals/eval_dataset.schema.json`。
- 评测集覆盖 `happy / boundary / adversarial / multi_hop` 四类。
- `release_manifest` 已绑定 `eval_dataset`、`judge_calibration` 和 `business_slo`。

## 3. Run Offline Golden Set Eval

离线 fixture 路径不依赖外部 LLM，也不依赖正在运行的 RAG API，适合课堂第一遍演示。

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m evals.run_ragas \
    --eval-set evals/sets/rag_qa_golden_v2_3_0.jsonl \
    --predictions evals/fixtures/week11/rag_predictions_good.jsonl \
    --release-id dev-week11-local \
    --output-dir reports/week11 \
    --report-file local-eval-report.json
```

Expected:

- 输出 `metrics`：`faithfulness / answer_relevance / context_precision / context_recall / answer_correctness / semantic_similarity`。
- 输出 `gate.status=pass`。
- 生成 `reports/week11/local-eval-report.json`。

课堂解释：

> 这一步不是假装生产 RAGAS，而是先把评测口径、报告结构和门禁行为跑通。真实 LLM judge 或 RAGAS 可以接同一份 eval report contract。

## 4. Run Regression Gate

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m evals.check_regression \
    --current reports/week11/local-eval-report.json \
    --baseline evals/baselines/week11_baseline_metrics.json \
    --max-drop faithfulness=0.02 \
    --max-drop answer_relevance=0.02 \
    --max-drop context_precision=0.03 \
    --min pass_rate=0.80 \
    --no-drop adversarial_pass_rate \
    --no-drop safety_pass_rate
```

Expected:

```text
REGRESSION GATE: PASS
```

课堂解释：

> `--max-drop` 是允许轻微波动，`--no-drop` 是安全红线。反例库和 PII 安全不能退，这就是 Week11 “门禁有牙齿”的地方。

## 5. Calibrate Judge

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m evals.calibrate \
    --human-set evals/calibration/human_judge_gold_v1.jsonl \
    --out reports/week11/judge-calibration.json
```

Expected:

- `cohen_kappa >= 0.6`
- `trust_level=high`

课堂解释：

> LLM-as-Judge 不是写个 prompt 就完事。prompt 改了，裁判就变了，必须重跑校准。

## 6. A/B Decision Helper

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m evals.ab_test --effect 0.05
```

Expected:

- 输出检测 5% 效应所需的大致样本量。

课堂解释：

> A/B 不是“跑 30 条看哪个分高”。样本量不够时，分数差异可能只是噪声。

## 7. Optional: Run Against Local RAG API

如果 Week08 RAG API 已经启动，可以直接打真实服务：

```bash
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build postgres rag_api

docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m evals.run_ragas \
    --eval-set evals/sets/rag_qa_golden_v2_3_0.jsonl \
    --rag-api http://rag_api:8000 \
    --release-id dev-week11-rag-api \
    --output-dir reports/week11 \
    --report-file rag-api-eval-report.json
```

说明：

- 如果本地没有完整 Week07/08 索引数据，真实 RAG API 可能返回 no-answer 或低分。
- 课堂主路径建议先用离线 fixture 讲清楚评测体系，再演示 `--rag-api` 是如何替换数据来源的。

## 8. Run Week11 Tests

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/test_week11_eval_contracts.py tests/integration/test_week11_evaluation_system.py -v
```

Expected:

- 契约、runner、regression gate、judge calibration、A/B helper、business SLO 全部通过。

## 9. Mental Model

不要把 Week11 讲成“多跑几个测试”。应该这样讲：

> Week11 是把 Copilot 的质量做成一条发布控制链：评测集定尺子，指标定刻度，judge 定裁判，gate 给否决权，business SLO 把技术分翻译成业务结果。

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `eval set must include all Week11 categories` | golden set 少了四类中的某一类 | 补 `happy / boundary / adversarial / multi_hop` 样本 |
| `REGRESSION GATE: FAIL` | 当前报告低于 baseline 或安全红线退化 | 先看失败 metric，再定位检索、生成、反例库哪层坏了 |
| `trust_level=low` | judge 分数和人工金标准不一致 | 重写 judge prompt，补 calibration example，再重跑 |
| 真实 RAG API 分数低 | 本地没有完整索引或证据数据 | 先跑 Week07/08 数据准备，或课堂先用离线 fixture |


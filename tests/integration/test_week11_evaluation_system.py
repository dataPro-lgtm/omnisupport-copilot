import asyncio
import json
import sys
from pathlib import Path

import jsonschema

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.week11.ab_test import compare, required_sample_size
from evals.week11.business_slo import evaluate_business_slo
from evals.week11.calibrate import calibration_report, load_score_pairs
from evals.week11.regression import check_regression, load_metrics
from evals.week11.runner import EvaluationRunner, write_report


DATASET = PROJECT_ROOT / "evals" / "sets" / "rag_qa_golden_v2_3_0.jsonl"
PREDICTIONS = PROJECT_ROOT / "evals" / "fixtures" / "week11" / "rag_predictions_good.jsonl"
BASELINE = PROJECT_ROOT / "evals" / "baselines" / "week11_baseline_metrics.json"
REPORT_SCHEMA = PROJECT_ROOT / "contracts" / "evals" / "eval_report.schema.json"
CALIBRATION_SET = PROJECT_ROOT / "evals" / "calibration" / "human_judge_gold_v1.jsonl"


def test_week11_runner_generates_eval_report(tmp_path: Path):
    runner = EvaluationRunner(release_id="dev-week11-test")
    report = asyncio.run(
        runner.run_with_predictions(eval_set_path=DATASET, predictions_path=PREDICTIONS)
    )
    report_path = write_report(report, tmp_path, "report.json")

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, json.loads(REPORT_SCHEMA.read_text(encoding="utf-8")))
    assert payload["gate"]["status"] == "pass"
    assert payload["metrics"]["pass_rate"] >= 0.80
    assert payload["metrics"]["adversarial_pass_rate"] == 1.0
    assert payload["category_breakdown"]["multi_hop"]["total"] == 2


def test_week11_regression_gate_accepts_current_fixture(tmp_path: Path):
    runner = EvaluationRunner(release_id="dev-week11-test")
    report = asyncio.run(
        runner.run_with_predictions(eval_set_path=DATASET, predictions_path=PREDICTIONS)
    )
    report_path = write_report(report, tmp_path, "report.json")

    failures = check_regression(
        current=load_metrics(report_path),
        baseline=load_metrics(BASELINE),
        max_drop={"faithfulness": 0.02, "answer_relevance": 0.02, "context_precision": 0.03},
        min_values={"pass_rate": 0.80},
        no_drop=["adversarial_pass_rate", "safety_pass_rate"],
    )
    assert failures == []


def test_week11_judge_calibration_reports_trust_level():
    report = calibration_report(load_score_pairs(CALIBRATION_SET))
    assert report["sample_count"] == 8
    assert report["cohen_kappa"] >= 0.6
    assert report["trust_level"] == "high"


def test_week11_ab_test_returns_decision_shape():
    assert required_sample_size(effect=0.1) < required_sample_size(effect=0.05)
    result = compare([0.72, 0.74, 0.73, 0.75, 0.74], [0.84, 0.86, 0.85, 0.87, 0.86])
    assert result["diff"] > 0
    assert result["recommendation"] in {"ship_B", "need_more_data"}


def test_week11_business_slo_eval_distinguishes_red_lines():
    report = evaluate_business_slo(
        {
            "first_resolution_rate": {"target": 0.65, "current": 0.68},
            "pii_leak_rate": {"target": "=0", "current": 0},
            "cost_per_ticket": {"target": "<3.0", "current": 2.4},
        }
    )
    assert report["status"] == "pass"
    failed = evaluate_business_slo({"pii_leak_rate": {"target": "=0", "current": 1}})
    assert failed["status"] == "fail"

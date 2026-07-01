"""Week11 evaluation runner."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.week11.dataset import dataset_digest, load_eval_set
from evals.week11.metrics import score_case
from evals.week11.models import EvalCaseResult, EvalPrediction, EvalReport, EvalSample


DEFAULT_DATASET_ID = "rag_qa_golden_v2"
DEFAULT_DATASET_VERSION = "2.3.0"


class EvaluationRunner:
    def __init__(
        self,
        *,
        release_id: str,
        dataset_id: str = DEFAULT_DATASET_ID,
        dataset_version: str = DEFAULT_DATASET_VERSION,
    ) -> None:
        self.release_id = release_id
        self.dataset_id = dataset_id
        self.dataset_version = dataset_version

    async def run_with_predictions(
        self,
        *,
        eval_set_path: Path,
        predictions_path: Path,
    ) -> EvalReport:
        samples = load_eval_set(eval_set_path)
        predictions = _load_predictions(predictions_path)
        results = [
            EvalCaseResult(
                sample=sample,
                prediction=predictions.get(sample.case_id, _missing_prediction(sample)),
                scores=score_case(sample, predictions.get(sample.case_id, _missing_prediction(sample))),
            )
            for sample in samples
        ]
        return self._report(eval_set_path, results)

    async def run_against_rag_api(
        self,
        *,
        eval_set_path: Path,
        rag_api_url: str,
        concurrency: int = 3,
        timeout: float = 30.0,
    ) -> EvalReport:
        samples = load_eval_set(eval_set_path)
        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(sample: EvalSample) -> EvalCaseResult:
            async with semaphore:
                prediction = await _call_rag_api(sample, rag_api_url, timeout=timeout)
                return EvalCaseResult(
                    sample=sample,
                    prediction=prediction,
                    scores=score_case(sample, prediction),
                )

        results = await asyncio.gather(*[run_one(sample) for sample in samples])
        return self._report(eval_set_path, list(results))

    def _report(self, eval_set_path: Path, results: list[EvalCaseResult]) -> EvalReport:
        gate = _gate_decision(results)
        eval_run_id = f"eval-week11-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        return EvalReport.create(
            eval_run_id=eval_run_id,
            release_id=self.release_id,
            dataset_id=self.dataset_id,
            dataset_version=self.dataset_version,
            dataset_digest=dataset_digest(eval_set_path),
            results=results,
            gate=gate,
        )


def _load_predictions(path: Path) -> dict[str, EvalPrediction]:
    predictions: dict[str, EvalPrediction] = {}
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            prediction = EvalPrediction.from_mapping(data)
            if not prediction.case_id:
                raise ValueError(f"{path}:{lineno}: prediction case_id is required")
            predictions[prediction.case_id] = prediction
    return predictions


async def _call_rag_api(sample: EvalSample, rag_api_url: str, *, timeout: float) -> EvalPrediction:
    import httpx

    base = rag_api_url.rstrip("/")
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base}/rag/answer",
            json={
                "question": sample.query,
                "product_line": sample.product_line if sample.product_line != "any" else None,
                "top_k": 5,
                "include_debug": True,
            },
        )
        response.raise_for_status()
        payload = response.json()
    payload["case_id"] = sample.case_id
    payload["latency_ms"] = (time.perf_counter() - started) * 1000
    return EvalPrediction.from_mapping(payload)


def _missing_prediction(sample: EvalSample) -> EvalPrediction:
    return EvalPrediction(
        case_id=sample.case_id,
        answer="",
        contexts=[],
        citations=[],
        confidence=0.0,
        trace_id="missing",
        abstain_reason="missing_prediction",
    )


def _gate_decision(results: list[EvalCaseResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item.scores.passed)
    adversarial = [item for item in results if item.sample.category == "adversarial"]
    adversarial_passed = sum(1 for item in adversarial if item.scores.passed)
    pass_rate = passed / max(total, 1)
    adversarial_pass_rate = adversarial_passed / max(len(adversarial), 1)
    blocking_reasons = []
    if pass_rate < 0.80:
        blocking_reasons.append(f"pass_rate_below_0.80:{pass_rate:.3f}")
    if adversarial and adversarial_pass_rate < 1.0:
        blocking_reasons.append("adversarial_regression_detected")
    if any(not item.scores.safety_pass for item in results):
        blocking_reasons.append("safety_regression_detected")
    return {
        "status": "pass" if not blocking_reasons else "fail",
        "pass_rate": round(pass_rate, 6),
        "adversarial_pass_rate": round(adversarial_pass_rate, 6),
        "blocking_reasons": blocking_reasons,
    }


def write_report(report: EvalReport, output_dir: Path, report_file: str | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / (report_file or f"{report.eval_run_id}.json")
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Week11 OmniSupport eval harness")
    parser.add_argument("--eval-set", type=Path, required=True)
    parser.add_argument("--release-id", default="dev-week11-local")
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID)
    parser.add_argument("--dataset-version", default=DEFAULT_DATASET_VERSION)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--rag-api", default="")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/week11"))
    parser.add_argument("--report-file", default=None)
    args = parser.parse_args(argv)

    runner = EvaluationRunner(
        release_id=args.release_id,
        dataset_id=args.dataset_id,
        dataset_version=args.dataset_version,
    )
    if args.predictions:
        report = asyncio.run(
            runner.run_with_predictions(eval_set_path=args.eval_set, predictions_path=args.predictions)
        )
    elif args.rag_api:
        report = asyncio.run(
            runner.run_against_rag_api(
                eval_set_path=args.eval_set,
                rag_api_url=args.rag_api,
                concurrency=args.concurrency,
            )
        )
    else:
        raise SystemExit("Either --predictions or --rag-api is required")

    path = write_report(report, args.output_dir, args.report_file)
    print(json.dumps({k: report.to_dict()[k] for k in ["eval_run_id", "metrics", "gate"]}, ensure_ascii=False, indent=2))
    print(f"report_path={path}")
    return 0 if report.gate["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

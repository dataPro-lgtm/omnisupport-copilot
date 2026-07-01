"""Regression gate comparison for Week11 eval reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_metrics(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "metrics" in data:
        metrics = dict(data["metrics"])
        metrics.update({f"latency.{k}": v for k, v in data.get("latency", {}).items()})
        metrics.update({f"cost.{k}": v for k, v in data.get("cost", {}).items()})
        return {key: float(value) for key, value in metrics.items()}
    return {key: float(value) for key, value in data.items()}


def parse_metric_args(values: list[str]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for value in values:
        name, raw = value.split("=", 1)
        parsed[name] = float(raw)
    return parsed


def check_regression(
    *,
    current: dict[str, float],
    baseline: dict[str, float],
    max_drop: dict[str, float],
    min_values: dict[str, float],
    no_drop: list[str],
) -> list[str]:
    failures: list[str] = []
    for metric, allowed_drop in max_drop.items():
        if metric not in current or metric not in baseline:
            failures.append(f"{metric}:missing_metric")
            continue
        drop = baseline[metric] - current[metric]
        if drop > allowed_drop:
            failures.append(
                f"{metric}:drop {drop:.4f} exceeds {allowed_drop:.4f} "
                f"(baseline={baseline[metric]:.4f}, current={current[metric]:.4f})"
            )
    for metric, threshold in min_values.items():
        if current.get(metric, float("-inf")) < threshold:
            failures.append(f"{metric}:current {current.get(metric, 0.0):.4f} below {threshold:.4f}")
    for metric in no_drop:
        if metric not in current or metric not in baseline:
            failures.append(f"{metric}:missing_metric")
            continue
        if current[metric] < baseline[metric]:
            failures.append(
                f"{metric}:no_drop violated "
                f"(baseline={baseline[metric]:.4f}, current={current[metric]:.4f})"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Week11 eval regression thresholds")
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--max-drop", action="append", default=[])
    parser.add_argument("--min", dest="min_values", action="append", default=[])
    parser.add_argument("--no-drop", action="append", default=[])
    args = parser.parse_args(argv)

    failures = check_regression(
        current=load_metrics(args.current),
        baseline=load_metrics(args.baseline),
        max_drop=parse_metric_args(args.max_drop),
        min_values=parse_metric_args(args.min_values),
        no_drop=args.no_drop,
    )
    if failures:
        print("REGRESSION GATE: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("REGRESSION GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


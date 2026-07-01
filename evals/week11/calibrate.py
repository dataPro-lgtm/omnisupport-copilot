"""LLM-as-Judge calibration helpers.

This module calculates trust diagnostics from human gold scores and judge
scores. It does not call an online judge; production adapters can write the same
JSONL format and reuse the calibration math.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load_score_pairs(path: Path) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            pairs.append((float(data["human_score"]), float(data["judge_score"])))
    if not pairs:
        raise ValueError("calibration set is empty")
    return pairs


def calibration_report(pairs: list[tuple[float, float]], *, top_k: int = 20) -> dict:
    human = [pair[0] for pair in pairs]
    judge = [pair[1] for pair in pairs]
    k = min(top_k, len(pairs))
    return {
        "sample_count": len(pairs),
        "cohen_kappa": round(_cohen_kappa(_bucket(human), _bucket(judge)), 6),
        "pearson_r": round(_pearson(human, judge), 6),
        "mae": round(sum(abs(h - j) for h, j in pairs) / len(pairs), 6),
        "top_k_overlap": round(_top_k_overlap(human, judge, k), 6),
    } | {
        "trust_level": "high"
        if _cohen_kappa(_bucket(human), _bucket(judge)) >= 0.6
        else "low"
    }


def _bucket(values: list[float]) -> list[int]:
    return [round(value * 2) for value in values]


def _cohen_kappa(a: list[int], b: list[int]) -> float:
    if len(a) != len(b):
        raise ValueError("score vectors must have the same length")
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    labels = sorted(set(a) | set(b))
    expected = 0.0
    for label in labels:
        pa = sum(1 for x in a if x == label) / n
        pb = sum(1 for y in b if y == label) / n
        expected += pa * pb
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1 - expected)


def _pearson(a: list[float], b: list[float]) -> float:
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    den_a = math.sqrt(sum((x - mean_a) ** 2 for x in a))
    den_b = math.sqrt(sum((y - mean_b) ** 2 for y in b))
    return num / max(den_a * den_b, 1e-9)


def _top_k_overlap(a: list[float], b: list[float], k: int) -> float:
    top_a = {idx for idx, _ in sorted(enumerate(a), key=lambda item: item[1])[-k:]}
    top_b = {idx for idx, _ in sorted(enumerate(b), key=lambda item: item[1])[-k:]}
    return len(top_a & top_b) / max(k, 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate Week11 judge scores")
    parser.add_argument("--human-set", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = calibration_report(load_score_pairs(args.human_set))
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["trust_level"] == "high" else 1


if __name__ == "__main__":
    raise SystemExit(main())


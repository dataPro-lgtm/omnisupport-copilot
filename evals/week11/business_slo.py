"""Business SLO checks for Week11 release manifest examples."""

from __future__ import annotations

from typing import Any


def evaluate_business_slo(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    all_pass = True
    for name, spec in metrics.items():
        target = spec["target"]
        current = spec["current"]
        passed = _compare(current, target)
        results[name] = {"target": target, "current": current, "status": "pass" if passed else "fail"}
        all_pass = all_pass and passed
    return {"status": "pass" if all_pass else "fail", "metrics": results}


def _compare(current: float, target: float | str) -> bool:
    if isinstance(target, str):
        if target.startswith("<="):
            return current <= float(target[2:])
        if target.startswith("<"):
            return current < float(target[1:])
        if target.startswith(">="):
            return current >= float(target[2:])
        if target.startswith(">"):
            return current > float(target[1:])
        if target.startswith("="):
            return current == float(target[1:])
    return current >= float(target)


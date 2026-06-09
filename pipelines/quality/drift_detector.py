"""Deterministic drift checks for parse quality metrics."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DriftSignal:
    metric: str
    baseline: float
    current: float
    threshold: float
    drifted: bool


def compare_metric(current: float, baseline: float, *, metric: str, threshold: float = 0.1) -> DriftSignal:
    drifted = abs(current - baseline) > threshold
    return DriftSignal(
        metric=metric,
        baseline=baseline,
        current=current,
        threshold=threshold,
        drifted=drifted,
    )

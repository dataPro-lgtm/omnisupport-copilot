"""Quality report projection aligned with the Week07 lesson."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class QualityReport:
    gate_decision: str
    completeness_score: float
    noise_score: float
    evidence_score: float
    coherence_score: float
    metrics: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_quality_report(gate: Any) -> QualityReport:
    metrics = dict(getattr(gate, "metrics", {}) or {})
    chunk_count = max(int(metrics.get("chunk_count") or 0), 1)
    empty_count = int(metrics.get("empty_chunk_count") or 0)
    fallback_count = int(metrics.get("fallback_chunk_count") or 0)

    completeness_score = float(metrics.get("metadata_completeness") or 0.0)
    evidence_score = float(metrics.get("anchor_coverage") or 0.0)
    noise_score = max(0.0, 1.0 - (empty_count + fallback_count) / chunk_count)
    coherence_score = 1.0 if not getattr(gate, "errors", []) else 0.0

    status = getattr(gate, "quality_status", "warn")
    decision = "block" if status == "fail" else "warn" if status == "warn" else "pass"
    return QualityReport(
        gate_decision=decision,
        completeness_score=round(completeness_score, 4),
        noise_score=round(noise_score, 4),
        evidence_score=round(evidence_score, 4),
        coherence_score=round(coherence_score, 4),
        metrics=metrics,
        warnings=list(getattr(gate, "warnings", []) or []),
        errors=list(getattr(gate, "errors", []) or []),
    )

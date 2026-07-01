"""Week11 evaluation data models.

The models intentionally stay dependency-light so the classroom repo can run
evaluation gates without external judge services. Production judge adapters can
populate the same report shape later.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


EVAL_CATEGORIES = {"happy", "boundary", "adversarial", "multi_hop"}


@dataclass(frozen=True)
class EvalThresholds:
    faithfulness: float = 0.65
    answer_relevance: float = 0.60
    context_precision: float = 0.55
    context_recall: float = 0.50
    answer_correctness: float = 0.55
    semantic_similarity: float = 0.55

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "EvalThresholds":
        if not data:
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        values = {key: float(data[key]) for key in data if key in allowed}
        return cls(**values)


@dataclass(frozen=True)
class EvalSample:
    case_id: str
    category: str
    query: str
    expected_answer: str
    expected_keywords: list[str]
    expected_citation_ids: list[str]
    source_doc: str
    doc_version: str
    product_line: str = "any"
    expected_context_keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    thresholds: EvalThresholds = field(default_factory=EvalThresholds)
    should_abstain: bool = False
    forbidden_phrases: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "EvalSample":
        category = data["category"]
        if category not in EVAL_CATEGORIES:
            raise ValueError(f"Unsupported eval category: {category}")
        return cls(
            case_id=data["case_id"],
            category=category,
            query=data["query"],
            expected_answer=data["expected_answer"],
            expected_keywords=list(data.get("expected_keywords", [])),
            expected_citation_ids=list(data.get("expected_citation_ids", [])),
            source_doc=data.get("source_doc", ""),
            doc_version=data.get("doc_version", ""),
            product_line=data.get("product_line", "any"),
            expected_context_keywords=list(data.get("expected_context_keywords", [])),
            tags=list(data.get("tags", [])),
            thresholds=EvalThresholds.from_mapping(data.get("thresholds")),
            should_abstain=bool(data.get("should_abstain", False)),
            forbidden_phrases=list(data.get("forbidden_phrases", [])),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["thresholds"] = asdict(self.thresholds)
        return data


@dataclass(frozen=True)
class RetrievedContext:
    chunk_id: str
    text: str
    evidence_id: str | None = None
    score: float | None = None
    source_id: str | None = None
    doc_id: str | None = None
    page_no: int | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RetrievedContext":
        citation = data.get("citation") or data.get("evidence_anchor") or {}
        return cls(
            chunk_id=str(data.get("chunk_id") or data.get("section_id") or ""),
            text=str(data.get("content") or data.get("text") or data.get("quote") or ""),
            evidence_id=(
                data.get("evidence_id")
                or citation.get("evidence_id")
                or citation.get("chunk_id")
                or data.get("chunk_id")
            ),
            score=_maybe_float(data.get("score") or data.get("final_score")),
            source_id=data.get("source_id") or citation.get("source_id"),
            doc_id=data.get("doc_id") or citation.get("doc_id"),
            page_no=data.get("page_no") or citation.get("page_no"),
        )


@dataclass(frozen=True)
class EvalPrediction:
    case_id: str
    answer: str
    contexts: list[RetrievedContext]
    citations: list[str]
    confidence: float = 0.0
    trace_id: str = ""
    abstain_reason: str | None = None
    latency_ms: float = 0.0
    cost_usd: float = 0.0

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "EvalPrediction":
        citations = _normalise_citations(data.get("citations", []), data.get("evidence_ids", []))
        contexts_raw = data.get("retrieved_contexts") or data.get("retrieved_chunks") or data.get("contexts") or []
        return cls(
            case_id=data.get("case_id", ""),
            answer=str(data.get("answer", "")),
            contexts=[RetrievedContext.from_mapping(ctx) for ctx in contexts_raw],
            citations=citations,
            confidence=float(data.get("confidence", 0.0) or 0.0),
            trace_id=str(data.get("trace_id", "")),
            abstain_reason=data.get("abstain_reason"),
            latency_ms=float(data.get("latency_ms", 0.0) or 0.0),
            cost_usd=float(data.get("cost_usd", 0.0) or 0.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CaseScores:
    faithfulness: float
    answer_relevance: float
    context_precision: float
    context_recall: float
    answer_correctness: float
    semantic_similarity: float
    safety_pass: bool
    passed: bool
    failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvalCaseResult:
    sample: EvalSample
    prediction: EvalPrediction
    scores: CaseScores

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample": self.sample.to_dict(),
            "prediction": self.prediction.to_dict(),
            "scores": self.scores.to_dict(),
        }


@dataclass(frozen=True)
class EvalReport:
    eval_run_id: str
    release_id: str
    eval_dataset_id: str
    eval_dataset_version: str
    eval_dataset_digest: str
    run_at: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    category_breakdown: dict[str, dict[str, int | float]]
    metrics: dict[str, float]
    latency: dict[str, float]
    cost: dict[str, float]
    gate: dict[str, Any]
    results: list[EvalCaseResult]

    @classmethod
    def create(
        cls,
        *,
        eval_run_id: str,
        release_id: str,
        dataset_id: str,
        dataset_version: str,
        dataset_digest: str,
        results: list[EvalCaseResult],
        gate: dict[str, Any],
    ) -> "EvalReport":
        total = len(results)
        passed = sum(1 for item in results if item.scores.passed)
        failed = total - passed
        metrics = _average_metrics(results)
        latency_values = [item.prediction.latency_ms for item in results]
        cost_values = [item.prediction.cost_usd for item in results]
        return cls(
            eval_run_id=eval_run_id,
            release_id=release_id,
            eval_dataset_id=dataset_id,
            eval_dataset_version=dataset_version,
            eval_dataset_digest=dataset_digest,
            run_at=datetime.now(timezone.utc).isoformat(),
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            category_breakdown=_category_breakdown(results),
            metrics=metrics,
            latency={
                "avg_ms": _avg(latency_values),
                "p50_ms": _percentile(latency_values, 50),
                "p99_ms": _percentile(latency_values, 99),
            },
            cost={
                "total_usd": round(sum(cost_values), 6),
                "avg_per_query_usd": round(_avg(cost_values), 6),
            },
            gate=gate,
            results=results,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "eval_run_id": self.eval_run_id,
            "release_id": self.release_id,
            "eval_dataset_id": self.eval_dataset_id,
            "eval_dataset_version": self.eval_dataset_version,
            "eval_dataset_digest": self.eval_dataset_digest,
            "run_at": self.run_at,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "category_breakdown": self.category_breakdown,
            "metrics": self.metrics,
            "latency": self.latency,
            "cost": self.cost,
            "gate": self.gate,
            "results": [item.to_dict() for item in self.results],
        }


def _normalise_citations(citations: list[Any], evidence_ids: list[Any]) -> list[str]:
    values: list[str] = []
    for citation in citations:
        if isinstance(citation, str):
            values.append(citation)
        elif isinstance(citation, dict):
            for key in ("evidence_id", "chunk_id", "doc_id", "source_id"):
                if citation.get(key):
                    values.append(str(citation[key]))
    values.extend(str(item) for item in evidence_ids if item)
    return sorted(set(values))


def _average_metrics(results: list[EvalCaseResult]) -> dict[str, float]:
    names = [
        "faithfulness",
        "answer_relevance",
        "context_precision",
        "context_recall",
        "answer_correctness",
        "semantic_similarity",
    ]
    data = {name: round(_avg([getattr(item.scores, name) for item in results]), 6) for name in names}
    data["pass_rate"] = round(_avg([1.0 if item.scores.passed else 0.0 for item in results]), 6)
    data["adversarial_pass_rate"] = round(
        _avg(
            [
                1.0 if item.scores.passed else 0.0
                for item in results
                if item.sample.category == "adversarial"
            ]
        ),
        6,
    )
    data["safety_pass_rate"] = round(_avg([1.0 if item.scores.safety_pass else 0.0 for item in results]), 6)
    return data


def _category_breakdown(results: list[EvalCaseResult]) -> dict[str, dict[str, int | float]]:
    breakdown: dict[str, dict[str, int | float]] = {}
    for category in sorted(EVAL_CATEGORIES):
        items = [item for item in results if item.sample.category == category]
        passed = sum(1 for item in items if item.scores.passed)
        breakdown[category] = {
            "total": len(items),
            "passed": passed,
            "failed": len(items) - passed,
            "pass_rate": round(passed / len(items), 6) if items else 0.0,
        }
    return breakdown


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round((percentile / 100) * (len(ordered) - 1)))
    return round(ordered[idx], 3)


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


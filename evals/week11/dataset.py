"""Dataset loading, validation, and digest helpers for Week11."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from evals.week11.models import EVAL_CATEGORIES, EvalSample


def load_eval_set(path: Path) -> list[EvalSample]:
    samples: list[EvalSample] = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(EvalSample.from_mapping(json.loads(line)))
            except Exception as exc:  # pragma: no cover - message is what matters
                raise ValueError(f"{path}:{lineno}: invalid eval sample: {exc}") from exc
    validate_eval_set(samples)
    return samples


def validate_eval_set(samples: Iterable[EvalSample]) -> None:
    items = list(samples)
    if not items:
        raise ValueError("eval set is empty")
    case_ids = [item.case_id for item in items]
    duplicates = [case_id for case_id, count in Counter(case_ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate case_id values: {duplicates}")
    categories = {item.category for item in items}
    missing = EVAL_CATEGORIES - categories
    if missing:
        raise ValueError(f"eval set must include all Week11 categories; missing={sorted(missing)}")
    for item in items:
        if not item.expected_answer:
            raise ValueError(f"{item.case_id}: expected_answer is required")
        if not item.should_abstain and not item.expected_citation_ids:
            raise ValueError(f"{item.case_id}: expected_citation_ids required for answerable cases")


def dataset_digest(path: Path) -> str:
    payload = path.read_bytes()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def dataset_manifest(path: Path, *, dataset_id: str, version: str) -> dict:
    samples = load_eval_set(path)
    categories = Counter(sample.category for sample in samples)
    return {
        "id": dataset_id,
        "version": version,
        "path": str(path),
        "sample_count": len(samples),
        "categories": dict(sorted(categories.items())),
        "digest": dataset_digest(path),
        "source_docs": sorted({sample.source_doc for sample in samples if sample.source_doc}),
    }


"""Week07 report writers."""

from pathlib import Path

from pipelines.parse_normalize.models import ParseRunReport, write_json
from pipelines.parse_normalize.quality_gate import QualityGateResult


def write_quality_report_md(
    path: Path,
    *,
    gate: QualityGateResult,
    parse_run: ParseRunReport,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Week07 Chunk Quality Report",
        "",
        f"- Parse run: `{parse_run.parse_run_id}`",
        f"- Data release: `{parse_run.data_release_id}`",
        f"- Quality status: `{gate.quality_status}`",
        f"- Week8 ready: `{str(gate.week8_ready).lower()}`",
        "",
        "## Metrics",
        "",
    ]
    for key, value in gate.metrics.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{warning}`" for warning in gate.warnings] or ["- None"])
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- `{error}`" for error in gate.errors] or ["- None"])
    lines.extend(
        [
            "",
            "## Week8 Handoff",
            "",
            "- Week8 may index only chunks where `allowed_for_indexing=true`.",
            "- Citations must be generated from `evidence_anchors.json` or `evidence_anchor` rows.",
            "- Fallback parser output must not be treated as Docling-quality page/bbox evidence.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")
    return path


def write_week8_ready_gate(path: Path, gate: QualityGateResult, parse_run: ParseRunReport) -> Path:
    payload = {
        "data_release_id": parse_run.data_release_id,
        "parse_run_id": parse_run.parse_run_id,
        "chunk_strategy_version": parse_run.chunk_strategy_version,
        "parse_strategy_version": parse_run.parse_strategy_version,
        "quality_status": gate.quality_status,
        "week8_ready": gate.week8_ready,
        "metrics": gate.metrics,
        "warnings": gate.warnings,
        "errors": gate.errors,
        "consumer_rules": {
            "require_evidence_anchor": True,
            "reject_allowed_for_indexing_false": True,
            "citations_from_evidence_anchor_only": True,
            "respect_strategy_versions": True,
        },
    }
    return write_json(path, payload)

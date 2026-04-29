"""Week06 run evidence generation and validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from pipelines.resources.config import DataFactorySettings

SCHEMA_RELATIVE_PATH = Path("contracts/run_evidence/week06_run_evidence.schema.json")


@dataclass(frozen=True)
class RunEvidence:
    evidence_schema_version: str
    run_id: str
    asset_key: str
    partition_key: str
    status: str
    started_at: str
    finished_at: str
    report_path: str
    reason_codes: list[str]
    manifest_id: str | None = None
    batch_id: str | None = None
    input_row_count: int | None = None
    output_row_count: int | None = None
    source_snapshot_id: str | int | None = None
    output_snapshot_id: str | int | None = None
    dbt_invocation_id: str | None = None
    semantic_metric_count: int | None = None
    lakehouse_snapshot_id: str | int | None = None
    data_release_id: str | None = None
    trace_id: str | None = None
    git_sha: str | None = None
    downstream_decision: str | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_schema(settings: DataFactorySettings | None = None) -> dict:
    resolved = settings or DataFactorySettings.from_env()
    return json.loads((resolved.project_root / SCHEMA_RELATIVE_PATH).read_text())


def validate_run_evidence(payload: dict[str, Any], settings: DataFactorySettings | None = None) -> None:
    schema = load_schema(settings)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    validator.validate(payload)


def safe_file_stem(value: str) -> str:
    return value.replace("/", "__").replace(":", "_")


def write_run_evidence(record: RunEvidence, path: Path, settings: DataFactorySettings) -> Path:
    payload = record.to_dict()
    validate_run_evidence(payload, settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def build_downstream_decision(status: str, reason_codes: list[str], dry_run: bool) -> str:
    if status == "failed":
        return "hold_downstream"
    if dry_run or "dry_run_no_db_write" in reason_codes:
        return "dry_run_only"
    if status == "warning":
        return "manual_review_required"
    return "proceed_to_week07"


def write_markdown_summary(records: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Week06 Run Evidence Summary",
        "",
        "| asset_key | partition | status | reason_codes |",
        "|---|---|---|---|",
    ]
    for record in records:
        lines.append(
            "| {asset_key} | {partition_key} | {status} | {reason_codes} |".format(
                asset_key=record.get("asset_key", ""),
                partition_key=record.get("partition_key", ""),
                status=record.get("status", ""),
                reason_codes=", ".join(record.get("reason_codes", [])),
            )
        )
    path.write_text("\n".join(lines) + "\n")
    return path

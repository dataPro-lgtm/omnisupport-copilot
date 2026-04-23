"""Shared helpers for Week03 smoke reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports" / "week03"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_report_path(report_path: Path | None, default_name: str | None = None) -> Path | None:
    if report_path is not None:
        return report_path
    if default_name is None:
        return None
    return DEFAULT_REPORTS_DIR / default_name


def write_json_report(
    payload: dict[str, Any],
    report_path: Path | None = None,
    *,
    default_name: str | None = None,
) -> Path | None:
    final_path = resolve_report_path(report_path, default_name)
    if final_path is None:
        return None

    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return final_path


def summarize_status(*, errors: int = 0, warnings: int = 0, quarantined: int = 0, invalid: int = 0) -> str:
    if errors > 0 or invalid > 0:
        return "error"
    if quarantined > 0 or warnings > 0:
        return "warning"
    return "ok"


def recommend_recovery_action(
    *,
    errors: int = 0,
    invalid: int = 0,
    warnings: int = 0,
    quarantined: int = 0,
) -> str:
    if errors > 0 or invalid > 0:
        return "rerun_after_fix"
    if quarantined > 0:
        return "replay_after_repair"
    if warnings > 0:
        return "retry_after_metadata_repair"
    return "proceed_to_next_stage"

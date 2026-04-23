"""Minimal ingest checkpoint state for Week03."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "canonization" / "checkpoints" / "week03_ingest_state.json"
STATE_SCHEMA_VERSION = "week03_ingest_state_v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class IngestCheckpoint:
    source_id: str
    last_processed_cursor: str | None = None
    last_success_batch_id: str | None = None
    last_run_id: str | None = None
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_state_payload() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "checkpoints": [],
    }


def load_state(state_path: Path | None = None) -> dict[str, Any]:
    final_path = state_path or DEFAULT_STATE_PATH
    if not final_path.exists():
        return default_state_payload()

    payload = json.loads(final_path.read_text())
    payload.setdefault("schema_version", STATE_SCHEMA_VERSION)
    payload.setdefault("checkpoints", [])
    return payload


def save_state(payload: dict[str, Any], state_path: Path | None = None) -> Path:
    final_path = state_path or DEFAULT_STATE_PATH
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return final_path


def get_checkpoint(source_id: str, state_path: Path | None = None) -> IngestCheckpoint | None:
    payload = load_state(state_path)
    for item in payload.get("checkpoints", []):
        if item.get("source_id") == source_id:
            return IngestCheckpoint(**item)
    return None


def upsert_checkpoint(
    *,
    source_id: str,
    last_processed_cursor: str | None = None,
    last_success_batch_id: str | None = None,
    last_run_id: str | None = None,
    state_path: Path | None = None,
) -> IngestCheckpoint:
    payload = load_state(state_path)
    checkpoints = payload.setdefault("checkpoints", [])

    existing: dict[str, Any] | None = None
    for item in checkpoints:
        if item.get("source_id") == source_id:
            existing = item
            break

    checkpoint = IngestCheckpoint(
        source_id=source_id,
        last_processed_cursor=last_processed_cursor or (existing or {}).get("last_processed_cursor"),
        last_success_batch_id=last_success_batch_id or (existing or {}).get("last_success_batch_id"),
        last_run_id=last_run_id or (existing or {}).get("last_run_id"),
        updated_at=_utc_now(),
    )

    if existing is None:
        checkpoints.append(checkpoint.to_dict())
    else:
        existing.clear()
        existing.update(checkpoint.to_dict())

    save_state(payload, state_path)
    return checkpoint

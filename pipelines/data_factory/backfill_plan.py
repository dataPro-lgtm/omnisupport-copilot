"""Week06 backfill dry-run planner."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Iterable

from pipelines.resources.config import DataFactorySettings

VALID_MODES = {"dry-run"}


@dataclass(frozen=True)
class BackfillPlan:
    partition_key: str
    window_start: str
    window_end: str
    upstream_manifest_id: str | None
    expected_input_count: int
    current_output_count: int
    gap_reason: str
    proposed_action: str
    idempotency_guard: str
    downstream_impact: str
    operator: str
    timestamp: str
    mode: str = "dry-run"

    def to_dict(self) -> dict:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def partition_window(partition_key: str) -> tuple[str, str]:
    partition_date = date.fromisoformat(partition_key)
    start = datetime.combine(partition_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(partition_date, time.max, tzinfo=timezone.utc)
    return start.isoformat(), end.isoformat()


def iter_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def count_partition_rows(path: Path, partition_key: str) -> int:
    count = 0
    for record in iter_jsonl(path):
        created_at = str(record.get("created_at", ""))
        if created_at.startswith(partition_key):
            count += 1
    return count


def structured_manifest_id(settings: DataFactorySettings) -> str | None:
    if not settings.manifest_dir.exists():
        return None
    for path in sorted(settings.manifest_dir.glob("*.json")):
        if path.name.startswith("source_manifest"):
            continue
        data = json.loads(path.read_text())
        if data.get("modality") == "structured":
            return data.get("manifest_id")
    return None


def build_backfill_plan(
    partition_key: str,
    *,
    mode: str = "dry-run",
    settings: DataFactorySettings | None = None,
    operator: str | None = None,
    current_output_count: int = 0,
) -> BackfillPlan:
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported Week06 backfill mode: {mode}")

    resolved = settings or DataFactorySettings.from_env()
    window_start, window_end = partition_window(partition_key)
    expected_input_count = count_partition_rows(resolved.ticket_seed_path, partition_key)
    gap_reason = "no_gap_detected" if expected_input_count == current_output_count else "output_lag"

    return BackfillPlan(
        partition_key=partition_key,
        window_start=window_start,
        window_end=window_end,
        upstream_manifest_id=structured_manifest_id(resolved),
        expected_input_count=expected_input_count,
        current_output_count=current_output_count,
        gap_reason=gap_reason,
        proposed_action="dry_run_ticket_ingest_for_partition",
        idempotency_guard="ticket_id primary key plus raw source_fingerprint conflict guard",
        downstream_impact="Structured core only; Week04/Week05 remain observation-only in Week06",
        operator=operator or resolved.operator,
        timestamp=utc_now_iso(),
        mode=mode,
    )


def write_backfill_plan(plan: BackfillPlan, settings: DataFactorySettings) -> Path:
    settings.ensure_report_dirs()
    path = settings.backfill_dir / f"backfill_plan_{plan.partition_key}.json"
    path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Week06 backfill dry-run planner")
    parser.add_argument("--partition", required=True, help="daily partition key, e.g. 2026-04-17")
    parser.add_argument("--mode", choices=sorted(VALID_MODES), default="dry-run")
    parser.add_argument("--operator", default=None)
    parser.add_argument("--report-json", type=Path, default=None)
    args = parser.parse_args()

    settings = DataFactorySettings.from_env()
    plan = build_backfill_plan(
        args.partition,
        mode=args.mode,
        settings=settings,
        operator=args.operator,
    )
    path = args.report_json or write_backfill_plan(plan, settings)
    if args.report_json:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"report_path": settings.relative_to_root(path), **plan.to_dict()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

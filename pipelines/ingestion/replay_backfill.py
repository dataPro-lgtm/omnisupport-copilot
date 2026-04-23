"""Week03 dry-run recovery planner."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pipelines.ingestion.ingest_state import (
    DEFAULT_STATE_PATH,
    IngestCheckpoint,
    get_checkpoint,
)
from pipelines.ingestion.reporting import (
    recommend_recovery_action,
    summarize_status,
    utc_now_iso,
    write_json_report,
)

VALID_MODES = {"retry", "rerun", "replay", "backfill"}


@dataclass
class RecoveryPlan:
    mode: str
    source_id: str
    dry_run: bool
    batch_id: str | None = None
    start_cursor: str | None = None
    end_cursor: str | None = None
    checkpoint_snapshot: dict | None = None
    execution_plan: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommended_action: str = "proceed_to_next_stage"
    status: str = "ok"
    generated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


def _build_execution_plan(
    *,
    mode: str,
    source_id: str,
    checkpoint: IngestCheckpoint | None,
    batch_id: str | None,
    start_cursor: str | None,
    end_cursor: str | None,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    steps: list[str] = [
        f"Resolve source scope for {source_id}.",
        "Inspect the latest ingest checkpoint before taking recovery action.",
    ]

    if mode == "retry":
        steps.append("Retry the same logical run without widening the ingest window.")
        if batch_id:
            steps.append(f"Reuse batch boundary {batch_id} for retry correlation.")
        elif checkpoint and checkpoint.last_run_id:
            steps.append(f"Retry using the last recorded run id {checkpoint.last_run_id}.")
        else:
            warnings.append("No batch_id or last_run_id available; operator must choose the failed run manually.")
    elif mode == "rerun":
        steps.append("Rerun the declared ingest flow from the original source definition.")
        if batch_id:
            steps.append(f"Replay the same source selection as batch {batch_id}.")
        else:
            steps.append("Use the current manifest selection and regenerate the full smoke path.")
    elif mode == "replay":
        target_batch = batch_id or (checkpoint.last_success_batch_id if checkpoint else None)
        steps.append("Reprocess an already known historical batch from the raw zone.")
        if target_batch:
            steps.append(f"Replay batch {target_batch}.")
        else:
            warnings.append("No replay batch supplied and no last_success_batch_id in state.")
    elif mode == "backfill":
        steps.append("Construct a historical cursor window and run the batch in dry-run first.")
        if start_cursor and end_cursor:
            steps.append(f"Backfill cursor window from {start_cursor} to {end_cursor}.")
        else:
            warnings.append("Backfill mode expects both start_cursor and end_cursor.")
    else:
        raise ValueError(f"Unsupported recovery mode: {mode}")

    steps.append("Write a Week03 recovery decision report before touching downstream storage.")
    return steps, warnings


def build_recovery_plan(
    *,
    mode: str,
    source_id: str,
    dry_run: bool = True,
    batch_id: str | None = None,
    start_cursor: str | None = None,
    end_cursor: str | None = None,
    checkpoint: IngestCheckpoint | None = None,
) -> RecoveryPlan:
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported recovery mode: {mode}")

    execution_plan, warnings = _build_execution_plan(
        mode=mode,
        source_id=source_id,
        checkpoint=checkpoint,
        batch_id=batch_id,
        start_cursor=start_cursor,
        end_cursor=end_cursor,
    )

    status = summarize_status(warnings=len(warnings))
    recommendation = recommend_recovery_action(warnings=len(warnings))

    return RecoveryPlan(
        mode=mode,
        source_id=source_id,
        dry_run=dry_run,
        batch_id=batch_id,
        start_cursor=start_cursor,
        end_cursor=end_cursor,
        checkpoint_snapshot=checkpoint.to_dict() if checkpoint else None,
        execution_plan=execution_plan,
        warnings=warnings,
        recommended_action=recommendation,
        status=status,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Week03 replay/backfill dry-run planner")
    parser.add_argument("--mode", required=True, choices=sorted(VALID_MODES))
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-cursor", default=None)
    parser.add_argument("--end-cursor", default=None)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--report-json", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    checkpoint = get_checkpoint(args.source_id, args.state_path)
    plan = build_recovery_plan(
        mode=args.mode,
        source_id=args.source_id,
        dry_run=args.dry_run,
        batch_id=args.batch_id,
        start_cursor=args.start_cursor,
        end_cursor=args.end_cursor,
        checkpoint=checkpoint,
    )

    write_json_report(
        plan.to_dict(),
        args.report_json,
        default_name="recovery_decision_log.json",
    )
    print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Week04 time travel demonstration."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pipelines.lakehouse.catalog import CORE_TABLES, load_lakehouse_catalog


def run_time_travel_demo(table_name: str, snapshot_id: int | None = None) -> dict:
    catalog = load_lakehouse_catalog()
    table = catalog.load_table(table_name)
    snapshots = list(table.metadata.snapshots)

    if snapshot_id is None and snapshots:
        snapshot_id = snapshots[0].snapshot_id

    current_rows = _count_rows(table)
    historical_rows = None
    if snapshot_id is not None:
        historical_rows = _count_rows(table, snapshot_id=snapshot_id)

    return {
        "report_version": "week04_time_travel_demo_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "table": table_name,
        "snapshot_count": len(snapshots),
        "selected_snapshot_id": snapshot_id,
        "current_row_count": current_rows,
        "selected_snapshot_row_count": historical_rows,
        "status": "ok" if snapshots else "no_snapshots",
        "notes": [
            "Use this demo after at least one successful materialization.",
            "For a stronger classroom demo, run materialization twice before comparing snapshots.",
        ],
    }


def _count_rows(table, snapshot_id: int | None = None) -> int:
    scan = table.scan(snapshot_id=snapshot_id) if snapshot_id is not None else table.scan()
    return scan.to_arrow().num_rows


def _markdown(payload: dict) -> str:
    return "\n".join(
        [
            "# Week04 Time Travel Demo Report",
            "",
            f"- table: `{payload['table']}`",
            f"- snapshot_count: `{payload['snapshot_count']}`",
            f"- selected_snapshot_id: `{payload['selected_snapshot_id']}`",
            f"- current_row_count: `{payload['current_row_count']}`",
            f"- selected_snapshot_row_count: `{payload['selected_snapshot_row_count']}`",
            f"- status: `{payload['status']}`",
            "",
            "## Notes",
            "",
            *[f"- {note}" for note in payload["notes"]],
            "",
        ]
    )


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".md":
        path.write_text(_markdown(payload), encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week04 Iceberg time travel demo")
    parser.add_argument("--table", default="silver.ticket_fact", choices=CORE_TABLES)
    parser.add_argument("--snapshot-id", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    payload = run_time_travel_demo(args.table, args.snapshot_id)
    if args.out:
        _write(args.out, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0 if payload["status"] in {"ok", "no_snapshots"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Inspect Iceberg metadata for Week04 demos."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pipelines.lakehouse.catalog import CORE_TABLES, load_lakehouse_catalog


def inspect_table(table_name: str, view: str) -> dict:
    catalog = load_lakehouse_catalog()
    table = catalog.load_table(table_name)

    if view == "snapshots":
        rows = [
            {
                "snapshot_id": snapshot.snapshot_id,
                "parent_snapshot_id": snapshot.parent_snapshot_id,
                "sequence_number": snapshot.sequence_number,
                "timestamp_ms": snapshot.timestamp_ms,
                "operation": _snapshot_summary(snapshot).get("operation"),
                "summary": _snapshot_summary(snapshot),
            }
            for snapshot in table.metadata.snapshots
        ]
    elif view == "history":
        rows = [
            {
                "snapshot_id": entry.snapshot_id,
                "timestamp_ms": entry.timestamp_ms,
            }
            for entry in table.history()
        ]
    elif view == "files":
        rows = []
        try:
            for task in table.scan().plan_files():
                data_file = task.file
                rows.append(
                    {
                        "file_path": str(data_file.file_path),
                        "file_format": str(data_file.file_format),
                        "record_count": data_file.record_count,
                        "file_size_in_bytes": data_file.file_size_in_bytes,
                    }
                )
        except Exception as exc:
            rows.append({"error": str(exc)})
    elif view == "metadata-log":
        rows = [
            {
                "timestamp_ms": item.timestamp_ms,
                "metadata_file": item.metadata_file,
            }
            for item in table.metadata.metadata_log
        ]
    else:
        raise ValueError(f"Unsupported metadata view: {view}")

    return {
        "report_version": "week04_iceberg_metadata_inspection_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "table": table_name,
        "view": view,
        "row_count": len(rows),
        "rows": rows,
    }


def _snapshot_summary(snapshot) -> dict:
    summary = snapshot.summary
    if summary is None:
        return {}
    if hasattr(summary, "model_dump"):
        return summary.model_dump(mode="json")
    if hasattr(summary, "dict"):
        return summary.dict()
    return dict(summary)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Week04 Iceberg table metadata")
    parser.add_argument("--table", required=True, choices=CORE_TABLES)
    parser.add_argument(
        "--view",
        required=True,
        choices=("snapshots", "history", "files", "metadata-log"),
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    payload = inspect_table(args.table, args.view)
    if args.out:
        _write(args.out, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

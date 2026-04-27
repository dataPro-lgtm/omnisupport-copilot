"""Generate Week04 Iceberg baseline reports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pipelines.lakehouse.catalog import CORE_TABLES, load_lakehouse_catalog


def table_baseline(table_name: str) -> dict:
    catalog = load_lakehouse_catalog()
    table = catalog.load_table(table_name)
    files = _files(table)
    sizes = [item["file_size_in_bytes"] for item in files if item.get("file_size_in_bytes") is not None]
    snapshot = table.current_snapshot()
    return {
        "table": table_name,
        "row_count": table.scan().to_arrow().num_rows,
        "snapshot_count": len(table.metadata.snapshots),
        "file_count": len(files),
        "avg_file_size": sum(sizes) / len(sizes) if sizes else 0,
        "min_file_size": min(sizes) if sizes else 0,
        "max_file_size": max(sizes) if sizes else 0,
        "latest_snapshot_id": snapshot.snapshot_id if snapshot else None,
        "latest_snapshot_time_ms": snapshot.timestamp_ms if snapshot else None,
        "latest_operation": _snapshot_summary(snapshot).get("operation") if snapshot else None,
    }


def _files(table) -> list[dict]:
    rows = []
    try:
        for task in table.scan().plan_files():
            rows.append(
                {
                    "file_path": str(task.file.file_path),
                    "record_count": task.file.record_count,
                    "file_size_in_bytes": task.file.file_size_in_bytes,
                }
            )
    except Exception:
        return []
    return rows


def _snapshot_summary(snapshot) -> dict:
    summary = snapshot.summary
    if summary is None:
        return {}
    if hasattr(summary, "model_dump"):
        return summary.model_dump(mode="json")
    if hasattr(summary, "dict"):
        return summary.dict()
    return dict(summary)


def baseline_report(tables: list[str]) -> dict:
    return {
        "report_version": "week04_iceberg_baseline_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tables": [table_baseline(table) for table in tables],
        "known_limits": [
            "Week04 records current table health and metadata shape; it does not run compaction.",
            "Partition distribution is omitted for unpartitioned Student Core Pack tables.",
        ],
        "next_steps": [
            "Use this report as the before/after baseline for Week05 transform and Week06 orchestration.",
            "Only introduce maintenance jobs after table growth justifies them.",
        ],
    }


def _markdown(payload: dict) -> str:
    lines = [
        "# Week04 Iceberg Baseline Report",
        "",
        f"generated_at: `{payload['generated_at']}`",
        "",
        "| table | rows | snapshots | files | avg file size | latest operation |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in payload["tables"]:
        lines.append(
            "| {table} | {row_count} | {snapshot_count} | {file_count} | {avg_file_size:.1f} | {latest_operation} |".format(
                **item
            )
        )
    lines.extend(["", "## Known Limits", ""])
    lines.extend(f"- {item}" for item in payload["known_limits"])
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {item}" for item in payload["next_steps"])
    lines.append("")
    return "\n".join(lines)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".md":
        path.write_text(_markdown(payload), encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Week04 Iceberg performance baseline")
    parser.add_argument("--all-core", action="store_true")
    parser.add_argument("--table", choices=CORE_TABLES)
    parser.add_argument("--out", type=Path, default=Path("reports/week04/iceberg_baseline_report.md"))
    args = parser.parse_args()

    tables = list(CORE_TABLES) if args.all_core else [args.table] if args.table else []
    if not tables:
        raise SystemExit("Use --all-core or --table <namespace.table>.")

    payload = baseline_report(tables)
    _write(args.out, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

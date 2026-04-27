"""Week04 schema evolution demonstration.

Only additive columns are allowed in Week04. Rename/drop/retype is deliberately
out of scope for this course week.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pipelines.lakehouse.catalog import CORE_TABLES, load_lakehouse_catalog


def run_schema_evolution_demo(table_name: str, add_column: str) -> dict:
    from pyiceberg.types import StringType

    catalog = load_lakehouse_catalog()
    table = catalog.load_table(table_name)
    before = [field.name for field in table.schema().fields]

    changed = False
    if add_column not in before:
        with table.update_schema() as update:
            update.add_column(path=add_column, field_type=StringType())
        changed = True

    after_table = catalog.load_table(table_name)
    after = [field.name for field in after_table.schema().fields]
    snapshot = after_table.current_snapshot()
    return {
        "report_version": "week04_schema_evolution_demo_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "table": table_name,
        "operation": "add_column",
        "column": add_column,
        "changed": changed,
        "before_columns": before,
        "after_columns": after,
        "current_snapshot_id": snapshot.snapshot_id if snapshot else None,
        "status": "ok",
    }


def _markdown(payload: dict) -> str:
    return "\n".join(
        [
            "# Week04 Schema Evolution Demo Report",
            "",
            f"- table: `{payload['table']}`",
            f"- operation: `{payload['operation']}`",
            f"- column: `{payload['column']}`",
            f"- changed: `{payload['changed']}`",
            f"- current_snapshot_id: `{payload['current_snapshot_id']}`",
            "",
            "## After Columns",
            "",
            *[f"- `{column}`" for column in payload["after_columns"]],
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
    parser = argparse.ArgumentParser(description="Run Week04 additive schema evolution demo")
    parser.add_argument("--table", default="bronze.raw_doc_asset", choices=CORE_TABLES)
    parser.add_argument("--add-column", default="source_checksum_algo")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    payload = run_schema_evolution_demo(args.table, args.add_column)
    if args.out:
        _write(args.out, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

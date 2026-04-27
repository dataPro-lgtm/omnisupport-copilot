import asyncio

import pytest


def test_week4_materialize_all_core_dry_run_reads_sources():
    pytest.importorskip("pyiceberg")
    pytest.importorskip("pyarrow")

    from pipelines.lakehouse.catalog import CORE_TABLES
    from pipelines.lakehouse.materialize import materialize_tables

    payload = asyncio.run(materialize_tables(CORE_TABLES, dry_run=True))
    assert payload["report_version"] == "week04_lakehouse_materialization_v1"
    assert set(payload["tables"]) == set(CORE_TABLES)
    for result in payload["tables"].values():
        assert result["action"] == "dry_run"
        assert result["source_rows"] >= 0

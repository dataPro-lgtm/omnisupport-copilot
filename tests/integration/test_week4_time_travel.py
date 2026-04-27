import pytest


def test_week4_time_travel_demo_reports_snapshot_state():
    pytest.importorskip("pyiceberg")
    pytest.importorskip("pyarrow")

    from pipelines.lakehouse.catalog import ensure_core_tables
    from pipelines.lakehouse.demo_time_travel import run_time_travel_demo

    ensure_core_tables(tables=("silver.ticket_fact",))
    payload = run_time_travel_demo("silver.ticket_fact")
    assert payload["report_version"] == "week04_time_travel_demo_v1"
    assert payload["status"] in {"ok", "no_snapshots"}
    assert payload["snapshot_count"] >= 0

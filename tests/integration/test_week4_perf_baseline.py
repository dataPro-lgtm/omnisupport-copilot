import pytest


def test_week4_perf_baseline_can_report_core_table():
    pytest.importorskip("pyiceberg")
    pytest.importorskip("pyarrow")

    from pipelines.lakehouse.catalog import ensure_core_tables
    from pipelines.lakehouse.perf_baseline import baseline_report

    ensure_core_tables(tables=("silver.ticket_fact",))
    payload = baseline_report(["silver.ticket_fact"])
    assert payload["report_version"] == "week04_iceberg_baseline_v1"
    assert payload["tables"][0]["table"] == "silver.ticket_fact"
    assert payload["tables"][0]["row_count"] >= 0

import pytest


def test_week4_catalog_smoke_loads_and_ensures_core_tables():
    pytest.importorskip("pyiceberg")
    pytest.importorskip("pyarrow")

    from pipelines.lakehouse.catalog import CORE_TABLES, smoke_check

    payload = smoke_check()
    assert payload["ok"] is True
    assert set(payload["tables"]) == set(CORE_TABLES)
    assert payload["bucket"]["bucket"] == "omni-lakehouse"

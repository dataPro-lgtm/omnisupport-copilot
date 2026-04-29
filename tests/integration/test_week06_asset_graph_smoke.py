from pathlib import Path

from dagster import materialize

from pipelines.data_factory.assets import WEEK06_ASSETS

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_week06_asset_graph_materializes_default_partition(monkeypatch, tmp_path):
    monkeypatch.setenv("WEEK06_PROJECT_ROOT", str(PROJECT_ROOT))
    monkeypatch.setenv("WEEK06_REPORT_DIR", str(tmp_path / "week06"))
    monkeypatch.setenv("SEED_MANIFEST_PATH", "data/seed_manifests")
    monkeypatch.setenv("WEEK06_TICKET_SEED_PATH", "data/canonization/tickets/tickets-seed-001.jsonl")
    monkeypatch.setenv("WEEK06_INGEST_DRY_RUN", "true")
    monkeypatch.setenv("WEEK06_WEEK04_REPORT_PATH", str(tmp_path / "missing_week04.json"))
    monkeypatch.setenv("WEEK06_WEEK05_RUN_RESULTS_PATH", str(tmp_path / "missing_week05.json"))
    monkeypatch.setenv("METRIC_REGISTRY_PATH", "analytics/metric_registry_v1.yml")

    result = materialize(WEEK06_ASSETS, partition_key="2026-04-17")

    assert result.success
    evidence_files = list((tmp_path / "week06" / "run_evidence").glob("*.json"))
    assert evidence_files
    assert (tmp_path / "week06" / "week06_delivery_summary.md").exists()

from pathlib import Path

from pipelines.data_factory.backfill_plan import build_backfill_plan, write_backfill_plan
from pipelines.resources.config import DataFactorySettings

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_week06_backfill_plan_uses_daily_partition(monkeypatch, tmp_path):
    monkeypatch.setenv("WEEK06_PROJECT_ROOT", str(PROJECT_ROOT))
    monkeypatch.setenv("WEEK06_REPORT_DIR", str(tmp_path / "week06"))
    monkeypatch.setenv("SEED_MANIFEST_PATH", "data/seed_manifests")
    monkeypatch.setenv("WEEK06_TICKET_SEED_PATH", "data/canonization/tickets/tickets-seed-001.jsonl")

    settings = DataFactorySettings.from_env()
    plan = build_backfill_plan("2026-04-17", settings=settings)
    report_path = write_backfill_plan(plan, settings)

    assert plan.partition_key == "2026-04-17"
    assert plan.mode == "dry-run"
    assert plan.expected_input_count > 0
    assert plan.current_output_count == 0
    assert plan.proposed_action == "dry_run_ticket_ingest_for_partition"
    assert report_path.exists()

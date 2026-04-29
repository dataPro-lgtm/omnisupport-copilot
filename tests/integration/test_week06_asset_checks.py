from pathlib import Path

from pipelines.data_factory.checks import run_week06_asset_checks, write_asset_checks_summary
from pipelines.resources.config import DataFactorySettings

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_week06_asset_checks_cover_student_core(monkeypatch, tmp_path):
    monkeypatch.setenv("WEEK06_PROJECT_ROOT", str(PROJECT_ROOT))
    monkeypatch.setenv("WEEK06_REPORT_DIR", str(tmp_path / "week06"))
    monkeypatch.setenv("SEED_MANIFEST_PATH", "data/seed_manifests")
    monkeypatch.setenv("WEEK06_TICKET_SEED_PATH", "data/canonization/tickets/tickets-seed-001.jsonl")

    settings = DataFactorySettings.from_env()
    outcomes = run_week06_asset_checks(
        partition_key="2026-04-17",
        settings=settings,
        ingest_stats={"total": 500, "valid": 500},
    )
    summary_path = write_asset_checks_summary(outcomes, settings)

    assert len(outcomes) >= 5
    assert {outcome.name for outcome in outcomes} >= {
        "manifest_consistency",
        "row_count_output_count",
        "duplicate_idempotency",
        "required_field_null_rate",
        "partition_completeness",
    }
    assert all(outcome.status in {"passed", "warning", "skipped"} for outcome in outcomes)
    assert (PROJECT_ROOT / summary_path if not Path(summary_path).is_absolute() else Path(summary_path)).exists()

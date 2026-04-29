from pathlib import Path

from pipelines.data_factory.evidence import RunEvidence, utc_now_iso, write_run_evidence
from pipelines.resources.config import DataFactorySettings

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_week06_run_evidence_generation_validates_schema(monkeypatch, tmp_path):
    monkeypatch.setenv("WEEK06_PROJECT_ROOT", str(PROJECT_ROOT))
    monkeypatch.setenv("WEEK06_REPORT_DIR", str(tmp_path / "week06"))
    settings = DataFactorySettings.from_env()
    report_path = settings.run_evidence_dir / "pytest_run_evidence.json"
    now = utc_now_iso()
    record = RunEvidence(
        evidence_schema_version="week06_run_evidence_v1",
        run_id="week06-pytest",
        asset_key="week06/ops/run_evidence_report",
        partition_key="2026-04-17",
        status="skipped",
        started_at=now,
        finished_at=now,
        report_path=settings.relative_to_root(report_path),
        reason_codes=["dry_run_no_db_write"],
        manifest_id="manifest-tickets-synthetic-20260331-001",
        batch_id="batch-20260331-001",
        input_row_count=10,
        output_row_count=0,
        data_release_id="week06-dev-local",
        trace_id="pytest",
        git_sha="unknown",
        downstream_decision="dry_run_only",
        checks=[
            {
                "name": "manifest_consistency",
                "status": "passed",
                "reason_codes": [],
                "metadata": {"manifest_count": 1},
            }
        ],
    )

    written = write_run_evidence(record, report_path, settings)

    assert written.exists()
    assert "week06_run_evidence_v1" in written.read_text()

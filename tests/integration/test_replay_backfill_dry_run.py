from pipelines.ingestion.ingest_state import IngestCheckpoint
from pipelines.ingestion.replay_backfill import build_recovery_plan


def _checkpoint() -> IngestCheckpoint:
    return IngestCheckpoint(
        source_id="structured:tickets:test_source",
        last_processed_cursor="2026-04-20T00:00:00Z",
        last_success_batch_id="batch-test-001",
        last_run_id="seed-loader::batch-test-001",
    )


def test_recovery_plan_supports_all_week03_modes():
    modes = ["retry", "rerun", "replay", "backfill"]

    for mode in modes:
        plan = build_recovery_plan(
            mode=mode,
            source_id="structured:tickets:test_source",
            dry_run=True,
            batch_id="batch-test-001",
            start_cursor="2026-04-01T00:00:00Z",
            end_cursor="2026-04-20T00:00:00Z",
            checkpoint=_checkpoint(),
        )

        payload = plan.to_dict()
        assert payload["mode"] == mode
        assert payload["source_id"] == "structured:tickets:test_source"
        assert payload["dry_run"] is True
        assert isinstance(payload["execution_plan"], list)
        assert payload["execution_plan"]
        assert "status" in payload
        assert "recommended_action" in payload


def test_recovery_plan_rejects_invalid_mode():
    try:
        build_recovery_plan(
            mode="invalid",
            source_id="structured:tickets:test_source",
            checkpoint=_checkpoint(),
        )
    except ValueError as exc:
        assert "Unsupported recovery mode" in str(exc)
    else:
        raise AssertionError("build_recovery_plan should reject invalid mode")

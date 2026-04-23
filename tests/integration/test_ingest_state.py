from pathlib import Path

from pipelines.ingestion.ingest_state import (
    STATE_SCHEMA_VERSION,
    get_checkpoint,
    load_state,
    save_state,
    upsert_checkpoint,
)


def test_ingest_state_can_write_and_read_checkpoint(tmp_path: Path):
    state_path = tmp_path / "week03_state.json"
    save_state({"schema_version": STATE_SCHEMA_VERSION, "checkpoints": []}, state_path)

    checkpoint = upsert_checkpoint(
        source_id="structured:tickets:test_source",
        last_processed_cursor="2026-04-24T00:00:00Z",
        last_success_batch_id="batch-test-001",
        last_run_id="seed-loader::batch-test-001",
        state_path=state_path,
    )

    payload = load_state(state_path)
    loaded = get_checkpoint("structured:tickets:test_source", state_path)

    assert payload["schema_version"] == STATE_SCHEMA_VERSION
    assert len(payload["checkpoints"]) == 1
    assert checkpoint.source_id == "structured:tickets:test_source"
    assert loaded is not None
    assert loaded.last_processed_cursor == "2026-04-24T00:00:00Z"
    assert loaded.last_success_batch_id == "batch-test-001"
    assert loaded.last_run_id == "seed-loader::batch-test-001"
    assert loaded.updated_at

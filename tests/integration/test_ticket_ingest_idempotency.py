import asyncio
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.ingestion.db import acquire, close_pool
from pipelines.ingestion.ingest_state import get_checkpoint
from pipelines.ingestion.ticket_ingest import run_ingest, ticket_source_fingerprint


def _ticket(source_id: str, ticket_id: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "schema_version": "ticket_v1",
        "source_id": source_id,
        "ingest_batch_id": "batch-pytest-idempotency",
        "customer_id": "cust-pytest-idempotency",
        "org_id": "org-pytest-idempotency",
        "status": "open",
        "priority": "p3_medium",
        "category": "configuration",
        "product_line": "northstar_workspace",
        "product_version": "3.2.0",
        "subject": "Idempotent ingest pytest ticket",
        "description": "Verify replay/backfill does not duplicate raw bronze rows.",
        "error_codes": [],
        "asset_ids": [],
        "assignee_id": None,
        "sla_tier": "standard",
        "sla_due_at": "2026-04-18T00:00:00Z",
        "created_at": "2026-04-17T10:00:00Z",
        "updated_at": "2026-04-17T10:05:00Z",
        "resolved_at": None,
        "pii_level": "low",
        "pii_redacted": False,
        "quality_gate": "pass",
        "owner": "pytest",
        "tags": ["pytest", "idempotency"],
    }


async def _cleanup(source_id: str, ticket_id: str) -> None:
    async with acquire() as conn:
        await conn.execute("DELETE FROM raw_ticket_event WHERE source_id = $1", source_id)
        await conn.execute("DELETE FROM ticket_fact WHERE ticket_id = $1", ticket_id)
        await conn.execute("DELETE FROM customer_dim WHERE customer_id = $1", "cust-pytest-idempotency")


async def _raw_count(source_id: str, fingerprint: str) -> int:
    async with acquire() as conn:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM raw_ticket_event
            WHERE source_id = $1 AND source_fingerprint = $2
            """,
            source_id,
            fingerprint,
        )


def test_ticket_ingest_is_idempotent_and_writes_checkpoint(tmp_path: Path):
    source_id = "structured:tickets:pytest_idempotency"
    ticket_id = "TKT-20260417-999991"
    ticket = _ticket(source_id, ticket_id)
    input_path = tmp_path / "tickets.jsonl"
    state_path = tmp_path / "week03_ingest_state.json"
    input_path.write_text(json.dumps(ticket) + "\n", encoding="utf-8")
    fingerprint = ticket_source_fingerprint(ticket)

    async def scenario():
        try:
            await _cleanup(source_id, ticket_id)
            first = await run_ingest(
                input_path,
                "batch-pytest-idempotency-001",
                dry_run=False,
                report_path=tmp_path / "first_report.json",
                state_path=state_path,
            )
            second = await run_ingest(
                input_path,
                "batch-pytest-idempotency-001",
                dry_run=False,
                report_path=tmp_path / "second_report.json",
                state_path=state_path,
            )
            count = await _raw_count(source_id, fingerprint)
        finally:
            await _cleanup(source_id, ticket_id)
            await close_pool()
        return first, second, count

    first, second, count = asyncio.run(scenario())
    checkpoint = get_checkpoint(source_id, state_path)

    assert first["inserted"] == 1
    assert first["bronze_inserted"] == 1
    assert second["inserted"] == 0
    assert second["bronze_duplicates"] == 1
    assert count == 1
    assert checkpoint is not None
    assert checkpoint.last_processed_cursor == "2026-04-17T10:05:00Z"
    assert checkpoint.last_success_batch_id == "batch-pytest-idempotency-001"

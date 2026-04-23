"""Ticket Ingest Pipeline — 工单批量采集写入

从 JSONL seed 文件读取合成工单，校验契约，写入 PostgreSQL Bronze + Silver 层。

执行方式:
    python -m pipelines.ingestion.ticket_ingest \
        --input data/canonization/tickets/tickets-seed-001.jsonl \
        --batch-id batch-20260401-001
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import jsonschema

from pipelines.ingestion.reporting import (
    recommend_recovery_action,
    summarize_status,
    utc_now_iso,
    write_json_report,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
TICKET_SCHEMA_PATH = PROJECT_ROOT / "contracts" / "data" / "ticket_contract.json"


# ── Schema 加载 ───────────────────────────────────────────────────────────────

def _load_ticket_schema() -> dict:
    return json.loads(TICKET_SCHEMA_PATH.read_text()) if TICKET_SCHEMA_PATH.exists() else {}


# ── 行迭代 ────────────────────────────────────────────────────────────────────

async def iter_jsonl(path: Path) -> AsyncIterator[dict]:
    """逐行读取 JSONL，跳过空行和解析失败行"""
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Line {lineno}: invalid JSON — {e}")


# ── 校验 ──────────────────────────────────────────────────────────────────────

class TicketValidator:
    def __init__(self):
        self._schema = _load_ticket_schema()

    def validate(self, ticket: dict) -> list[str]:
        errors: list[str] = []
        if self._schema:
            try:
                jsonschema.validate(ticket, self._schema)
            except jsonschema.ValidationError as e:
                errors.append(f"schema: {e.message}")
        # 业务规则
        if not ticket.get("ticket_id", "").startswith("TKT-"):
            errors.append("ticket_id format invalid")
        if not ticket.get("created_at"):
            errors.append("created_at required")
        return errors


# ── 写入 DB ───────────────────────────────────────────────────────────────────

async def upsert_ticket_bronze(conn, ticket: dict, batch_id: str):
    """写入 raw_ticket_event Bronze 层"""
    fingerprint = hashlib.sha256(
        json.dumps(ticket, sort_keys=True).encode()
    ).hexdigest()

    await conn.execute(
        """
        INSERT INTO raw_ticket_event
            (source_id, manifest_id, ingest_batch_id, raw_payload,
             schema_version, license_tag, pii_level, source_fingerprint, ingest_ts)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (event_id) DO NOTHING
        """,
        ticket.get("source_id", "unknown"),
        ticket.get("source_id", ""),          # manifest_id 近似
        batch_id,
        json.dumps(ticket),
        ticket.get("schema_version", "ticket_v1"),
        ticket.get("license_tag", "course_synthetic"),
        ticket.get("pii_level", "low"),
        fingerprint,
        datetime.now(timezone.utc),
    )


async def upsert_ticket_silver(conn, ticket: dict, batch_id: str):
    """写入 ticket_fact Silver 层"""
    created_at = _parse_dt(ticket.get("created_at"))
    updated_at = _parse_dt(ticket.get("updated_at"))
    resolved_at = _parse_dt(ticket.get("resolved_at"))
    sla_due_at = _parse_dt(ticket.get("sla_due_at"))

    # 确保 customer_dim 记录存在（upsert）
    await conn.execute(
        """
        INSERT INTO customer_dim (customer_id, org_id, org_name, sla_tier)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (customer_id) DO UPDATE
            SET sla_tier = EXCLUDED.sla_tier,
                updated_at = NOW()
        """,
        ticket.get("customer_id"),
        ticket.get("org_id"),
        ticket.get("org_id", ""),   # org_name 未在 ticket 中，用 org_id 代替
        ticket.get("sla_tier", "standard"),
    )

    await conn.execute(
        """
        INSERT INTO ticket_fact (
            ticket_id, customer_id, org_id, status, priority, category,
            product_line, product_version, subject,
            error_codes, asset_ids, assignee_id,
            sla_tier, sla_due_at, created_at, updated_at, resolved_at,
            pii_level, pii_redacted, data_release_id, ingest_batch_id, schema_version
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22
        )
        ON CONFLICT (ticket_id) DO UPDATE SET
            status        = EXCLUDED.status,
            updated_at    = EXCLUDED.updated_at,
            resolved_at   = EXCLUDED.resolved_at,
            data_release_id = EXCLUDED.data_release_id
        """,
        ticket["ticket_id"],
        ticket.get("customer_id"),
        ticket.get("org_id"),
        ticket.get("status", "open"),
        ticket.get("priority", "p3_medium"),
        ticket.get("category", "other"),
        ticket.get("product_line"),
        ticket.get("product_version"),
        ticket.get("subject", ""),
        ticket.get("error_codes", []),
        ticket.get("asset_ids", []),
        ticket.get("assignee_id"),
        ticket.get("sla_tier", "standard"),
        sla_due_at,
        created_at,
        updated_at,
        resolved_at,
        ticket.get("pii_level", "low"),
        ticket.get("pii_redacted", False),
        ticket.get("data_release_id", "data-v0.1.0"),
        batch_id,
        ticket.get("schema_version", "ticket_v1"),
    )


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


# ── 主流程 ────────────────────────────────────────────────────────────────────

async def run_ingest(
    input_path: Path,
    batch_id: str,
    dry_run: bool = False,
    limit: int | None = None,
    report_path: Path | None = None,
) -> dict:
    from pipelines.ingestion.db import acquire

    validator = TicketValidator()

    stats = {
        "total": 0, "valid": 0, "invalid": 0,
        "inserted": 0, "skipped": 0, "errors": 0,
        "batch_id": batch_id,
        "input": str(input_path),
        "dry_run": dry_run,
    }

    if dry_run:
        async for ticket in iter_jsonl(input_path):
            if limit and stats["total"] >= limit:
                break

            stats["total"] += 1
            errs = validator.validate(ticket)
            if errs:
                stats["invalid"] += 1
                logger.warning(f"Ticket {ticket.get('ticket_id')} invalid: {errs}")
                continue

            stats["valid"] += 1

            stats["skipped"] += 1
            logger.debug(f"[dry-run] {ticket['ticket_id']}")
    else:
        async with acquire() as conn:
            async for ticket in iter_jsonl(input_path):
                if limit and stats["total"] >= limit:
                    break

                stats["total"] += 1
                errs = validator.validate(ticket)
                if errs:
                    stats["invalid"] += 1
                    logger.warning(f"Ticket {ticket.get('ticket_id')} invalid: {errs}")
                    continue

                stats["valid"] += 1

                try:
                    async with conn.transaction():
                        await upsert_ticket_bronze(conn, ticket, batch_id)
                        await upsert_ticket_silver(conn, ticket, batch_id)
                    stats["inserted"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"DB error for {ticket.get('ticket_id')}: {e}")

                if stats["total"] % 100 == 0:
                    logger.info(
                        f"Progress: {stats['total']} processed, "
                        f"{stats['inserted']} inserted, {stats['errors']} errors"
                    )

    _log_summary(stats)
    _write_ticket_report(stats, report_path)
    return stats


def _log_summary(stats: dict):
    logger.info(
        f"\n{'='*50}\n"
        f"  TICKET INGEST SUMMARY\n"
        f"  Batch    : {stats['batch_id']}\n"
        f"  Input    : {stats['input']}\n"
        f"  Total    : {stats['total']}\n"
        f"  Valid    : {stats['valid']}\n"
        f"  Invalid  : {stats['invalid']}\n"
        f"  Inserted : {stats['inserted']}\n"
        f"  Errors   : {stats['errors']}\n"
        f"{'='*50}"
    )


def _write_ticket_report(stats: dict, report_path: Path | None):
    payload = {
        "report_version": "week03_ticket_ingest_smoke_report_v1",
        "report_kind": "ticket_ingest_smoke",
        "run_id": f"ticket-ingest::{stats['batch_id']}",
        "generated_at": utc_now_iso(),
        "batch_id": stats["batch_id"],
        "input": stats["input"],
        "dry_run": stats["dry_run"],
        "summary": {
            "total": stats["total"],
            "valid": stats["valid"],
            "invalid": stats["invalid"],
            "inserted": stats["inserted"],
            "skipped": stats["skipped"],
            "errors": stats["errors"],
        },
        "status": summarize_status(errors=stats["errors"], invalid=stats["invalid"]),
        "recommended_action": recommend_recovery_action(
            errors=stats["errors"],
            invalid=stats["invalid"],
        ),
    }
    write_json_report(payload, report_path, default_name="ticket_ingest_smoke_report.json")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ticket Ingest Pipeline")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--batch-id", default=f"batch-{datetime.now(timezone.utc).strftime('%Y%m%d')}-001")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report-json", type=Path, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    stats = asyncio.run(
        run_ingest(args.input, args.batch_id, args.dry_run, args.limit, args.report_json)
    )
    sys.exit(1 if stats["errors"] > 0 else 0)


if __name__ == "__main__":
    main()

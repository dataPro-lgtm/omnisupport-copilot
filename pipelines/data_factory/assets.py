"""Week06 Dagster assets for the data factory layer."""

import asyncio
import json
import threading
from pathlib import Path
from typing import Any, Coroutine

from dagster import (
    AssetExecutionContext,
    AssetIn,
    MetadataValue,
    Output,
    asset,
)

from pipelines.data_factory.asset_keys import (
    BACKFILL_PLAN_KEY,
    DELIVERY_SUMMARY_KEY,
    LAKEHOUSE_STATE_KEY,
    MANIFEST_GATE_KEY,
    RAW_TICKET_EVENTS_KEY,
    RUN_EVIDENCE_KEY,
    SEED_MANIFESTS_KEY,
    SUPPORT_KPI_MART_KEY,
    TICKET_FACT_KEY,
    asset_key_to_str,
)
from pipelines.data_factory.backfill_plan import (
    build_backfill_plan,
    count_partition_rows,
    write_backfill_plan,
)
from pipelines.data_factory.checks import run_week06_asset_checks, write_asset_checks_summary
from pipelines.data_factory.evidence import (
    RunEvidence,
    build_downstream_decision,
    safe_file_stem,
    utc_now_iso,
    write_markdown_summary,
    write_run_evidence,
)
from pipelines.data_factory.partitions import default_partition_key, get_week06_partitions_def
from pipelines.ingestion.ticket_ingest import run_ingest
from pipelines.resources.config import DataFactorySettings

WEEK06_GROUP = "week06_data_factory"
WEEK06_PARTITIONS_DEF = get_week06_partitions_def()


def _partition_key(context: AssetExecutionContext | None, settings: DataFactorySettings) -> str:
    if context and context.has_partition_key:
        return context.partition_key
    return default_partition_key(settings)


def _run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async ingest function from Dagster's sync asset body."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:  # pragma: no cover - defensive bridge
            result["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _load_seed_manifests(settings: DataFactorySettings) -> list[dict]:
    if not settings.manifest_dir.exists():
        return []
    manifests: list[dict] = []
    for path in sorted(settings.manifest_dir.glob("*.json")):
        if path.name.startswith("source_manifest"):
            continue
        manifests.append(json.loads(path.read_text()))
    return manifests


def _select_structured_manifest(manifests: list[dict]) -> dict:
    for manifest in manifests:
        if manifest.get("modality") == "structured":
            return manifest
    return {}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _metric_registry_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        import yaml

        data = yaml.safe_load(path.read_text()) or {}
        metrics = data.get("metrics", [])
        return len(metrics) if isinstance(metrics, list) else None
    except Exception:
        return None


@asset(
    key=SEED_MANIFESTS_KEY,
    group_name=WEEK06_GROUP,
    partitions_def=WEEK06_PARTITIONS_DEF,
    description="Week06 source manifest discovery for the data factory.",
    tags={"week": "06", "layer": "source"},
)
def week06_source_seed_manifests(context: AssetExecutionContext) -> Output[list[dict]]:
    settings = DataFactorySettings.from_env()
    manifests = _load_seed_manifests(settings)
    partition_key = _partition_key(context, settings)

    return Output(
        manifests,
        metadata={
            "partition_key": MetadataValue.text(partition_key),
            "manifest_dir": MetadataValue.text(str(settings.manifest_dir)),
            "manifest_count": MetadataValue.int(len(manifests)),
            "manifest_ids": MetadataValue.json([m.get("manifest_id") for m in manifests]),
        },
    )


@asset(
    key=MANIFEST_GATE_KEY,
    ins={"seed_manifests": AssetIn(key=SEED_MANIFESTS_KEY)},
    group_name=WEEK06_GROUP,
    partitions_def=WEEK06_PARTITIONS_DEF,
    description="Admission gate that selects the structured ticket manifest.",
    tags={"week": "06", "layer": "factory"},
)
def week06_factory_manifest_gate(
    context: AssetExecutionContext,
    seed_manifests: list[dict],
) -> Output[dict]:
    settings = DataFactorySettings.from_env()
    partition_key = _partition_key(context, settings)
    manifest = _select_structured_manifest(seed_manifests)
    accepted = bool(manifest and manifest.get("assets"))
    reason_codes = [] if accepted else ["structured_manifest_missing_or_empty"]

    payload = {
        "status": "accepted" if accepted else "failed",
        "reason_codes": reason_codes,
        "manifest_id": manifest.get("manifest_id"),
        "batch_id": manifest.get("batch_id"),
        "asset_count": len(manifest.get("assets", [])) if manifest else 0,
        "partition_key": partition_key,
        "ticket_seed_path": str(settings.ticket_seed_path),
    }

    return Output(
        payload,
        metadata={
            "status": MetadataValue.text(payload["status"]),
            "manifest_id": MetadataValue.text(str(payload.get("manifest_id"))),
            "batch_id": MetadataValue.text(str(payload.get("batch_id"))),
            "asset_count": MetadataValue.int(payload["asset_count"]),
            "reason_codes": MetadataValue.json(reason_codes),
        },
    )


@asset(
    key=RAW_TICKET_EVENTS_KEY,
    ins={"manifest_gate": AssetIn(key=MANIFEST_GATE_KEY)},
    group_name=WEEK06_GROUP,
    partitions_def=WEEK06_PARTITIONS_DEF,
    description="Partitioned Week06 wrapper around the existing Week03 ticket ingest path.",
    tags={"week": "06", "layer": "ingestion"},
)
def week06_raw_ticket_events_partitioned(
    context: AssetExecutionContext,
    manifest_gate: dict,
) -> Output[dict]:
    settings = DataFactorySettings.from_env()
    settings.ensure_report_dirs()
    partition_key = _partition_key(context, settings)

    if manifest_gate.get("status") != "accepted":
        stats = {
            "status": "failed",
            "reason_codes": manifest_gate.get("reason_codes", []),
            "total": 0,
            "valid": 0,
            "inserted": 0,
            "errors": 1,
            "dry_run": settings.ingest_dry_run,
            "batch_id": manifest_gate.get("batch_id"),
            "partition_key": partition_key,
        }
    else:
        ingest_report = settings.checks_dir / f"ticket_ingest_stats_{partition_key}.json"
        stats = _run_async(
            run_ingest(
                settings.ticket_seed_path,
                manifest_gate.get("batch_id") or f"week06-{partition_key}",
                dry_run=settings.ingest_dry_run,
                limit=settings.ingest_limit,
                report_path=ingest_report,
            )
        )
        stats["status"] = "success" if stats.get("errors", 0) == 0 else "failed"
        stats["reason_codes"] = [] if stats["status"] == "success" else ["ticket_ingest_errors"]
        stats["partition_key"] = partition_key
        stats["partition_input_row_count"] = count_partition_rows(settings.ticket_seed_path, partition_key)
        stats["ingest_report_path"] = settings.relative_to_root(ingest_report)

    return Output(
        stats,
        metadata={
            "partition_key": MetadataValue.text(partition_key),
            "status": MetadataValue.text(stats["status"]),
            "input_row_count": MetadataValue.int(int(stats.get("total", 0))),
            "partition_input_row_count": MetadataValue.int(int(stats.get("partition_input_row_count", 0))),
            "valid_row_count": MetadataValue.int(int(stats.get("valid", 0))),
            "output_row_count": MetadataValue.int(int(stats.get("inserted", 0))),
            "dry_run": MetadataValue.bool(bool(stats.get("dry_run", settings.ingest_dry_run))),
        },
    )


@asset(
    key=TICKET_FACT_KEY,
    ins={"raw_ticket_events": AssetIn(key=RAW_TICKET_EVENTS_KEY)},
    group_name=WEEK06_GROUP,
    partitions_def=WEEK06_PARTITIONS_DEF,
    description="Structured silver delivery summary for ticket facts.",
    tags={"week": "06", "layer": "silver"},
)
def week06_ticket_fact_partitioned(
    context: AssetExecutionContext,
    raw_ticket_events: dict,
) -> Output[dict]:
    settings = DataFactorySettings.from_env()
    partition_key = _partition_key(context, settings)
    dry_run = bool(raw_ticket_events.get("dry_run", settings.ingest_dry_run))
    errors = int(raw_ticket_events.get("errors", 0))

    if errors > 0:
        status = "failed"
        reason_codes = ["ticket_ingest_errors"]
    elif dry_run:
        status = "skipped"
        reason_codes = ["dry_run_no_db_write"]
    else:
        status = "success"
        reason_codes = []

    output_row_count = 0 if dry_run else int(raw_ticket_events.get("inserted", 0))
    payload = {
        "status": status,
        "reason_codes": reason_codes,
        "partition_key": partition_key,
        "input_row_count": int(raw_ticket_events.get("valid", 0)),
        "output_row_count": output_row_count,
        "batch_id": raw_ticket_events.get("batch_id"),
        "dry_run": dry_run,
    }

    return Output(
        payload,
        metadata={
            "partition_key": MetadataValue.text(partition_key),
            "status": MetadataValue.text(status),
            "input_row_count": MetadataValue.int(payload["input_row_count"]),
            "output_row_count": MetadataValue.int(output_row_count),
            "reason_codes": MetadataValue.json(reason_codes),
        },
    )


@asset(
    key=LAKEHOUSE_STATE_KEY,
    group_name=WEEK06_GROUP,
    partitions_def=WEEK06_PARTITIONS_DEF,
    description="Observation-only Week04 lakehouse state for Week06 evidence.",
    tags={"week": "06", "layer": "external", "optional": "true"},
)
def week06_lakehouse_state(context: AssetExecutionContext) -> Output[dict]:
    settings = DataFactorySettings.from_env()
    partition_key = _partition_key(context, settings)
    report = _read_json(settings.week04_report_path)
    table = report.get("tables", {}).get("silver.ticket_fact", {}) if report else {}
    snapshot_id = table.get("snapshot_id")
    status = "success" if snapshot_id else "not_available"
    reason_codes = [] if snapshot_id else ["week04_lakehouse_not_available"]
    payload = {
        "status": status,
        "reason_codes": reason_codes,
        "partition_key": partition_key,
        "lakehouse_snapshot_id": snapshot_id,
        "report_path": settings.relative_to_root(settings.week04_report_path),
    }
    return Output(
        payload,
        metadata={
            "status": MetadataValue.text(status),
            "reason_codes": MetadataValue.json(reason_codes),
            "lakehouse_snapshot_id": MetadataValue.text(str(snapshot_id)),
        },
    )


@asset(
    key=SUPPORT_KPI_MART_KEY,
    group_name=WEEK06_GROUP,
    partitions_def=WEEK06_PARTITIONS_DEF,
    description="Observation-only Week05 support KPI mart state for Week06 evidence.",
    tags={"week": "06", "layer": "external", "optional": "true"},
)
def week06_support_kpi_mart(context: AssetExecutionContext) -> Output[dict]:
    settings = DataFactorySettings.from_env()
    partition_key = _partition_key(context, settings)
    run_results = _read_json(settings.week05_run_results_path)
    invocation_id = run_results.get("metadata", {}).get("invocation_id") if run_results else None
    metric_count = _metric_registry_count(settings.metric_registry_path)
    status = "success" if invocation_id else "not_available"
    reason_codes = [] if invocation_id else ["week05_analytics_not_available"]
    payload = {
        "status": status,
        "reason_codes": reason_codes,
        "partition_key": partition_key,
        "dbt_invocation_id": invocation_id,
        "semantic_metric_count": metric_count,
        "report_path": settings.relative_to_root(settings.week05_run_results_path),
    }
    return Output(
        payload,
        metadata={
            "status": MetadataValue.text(status),
            "reason_codes": MetadataValue.json(reason_codes),
            "dbt_invocation_id": MetadataValue.text(str(invocation_id)),
            "semantic_metric_count": MetadataValue.int(metric_count or 0),
        },
    )


@asset(
    key=BACKFILL_PLAN_KEY,
    group_name=WEEK06_GROUP,
    partitions_def=WEEK06_PARTITIONS_DEF,
    description="Week06 dry-run backfill plan for one daily partition.",
    tags={"week": "06", "layer": "ops"},
)
def week06_backfill_plan(context: AssetExecutionContext) -> Output[dict]:
    settings = DataFactorySettings.from_env()
    partition_key = _partition_key(context, settings)
    plan = build_backfill_plan(partition_key, settings=settings)
    path = write_backfill_plan(plan, settings)
    payload = {"report_path": settings.relative_to_root(path), **plan.to_dict()}
    return Output(
        payload,
        metadata={
            "partition_key": MetadataValue.text(partition_key),
            "expected_input_count": MetadataValue.int(plan.expected_input_count),
            "current_output_count": MetadataValue.int(plan.current_output_count),
            "gap_reason": MetadataValue.text(plan.gap_reason),
            "report_path": MetadataValue.path(str(path)),
        },
    )


@asset(
    key=RUN_EVIDENCE_KEY,
    ins={
        "ticket_fact": AssetIn(key=TICKET_FACT_KEY),
        "lakehouse_state": AssetIn(key=LAKEHOUSE_STATE_KEY),
        "support_kpi_mart": AssetIn(key=SUPPORT_KPI_MART_KEY),
        "backfill_plan": AssetIn(key=BACKFILL_PLAN_KEY),
    },
    group_name=WEEK06_GROUP,
    partitions_def=WEEK06_PARTITIONS_DEF,
    description="Schema-valid Week06 run evidence JSON and checks summary.",
    tags={"week": "06", "layer": "ops"},
)
def week06_run_evidence_report(
    context: AssetExecutionContext,
    ticket_fact: dict,
    lakehouse_state: dict,
    support_kpi_mart: dict,
    backfill_plan: dict,
) -> Output[dict]:
    settings = DataFactorySettings.from_env()
    settings.ensure_report_dirs()
    partition_key = _partition_key(context, settings)
    started_at = utc_now_iso()
    check_outcomes = run_week06_asset_checks(
        partition_key=partition_key,
        settings=settings,
        ingest_stats={
            "total": ticket_fact.get("input_row_count", 0),
            "valid": ticket_fact.get("input_row_count", 0),
        },
    )
    checks_path = write_asset_checks_summary(check_outcomes, settings)
    check_payloads = [outcome.to_dict() for outcome in check_outcomes]
    failed_checks = [outcome.name for outcome in check_outcomes if outcome.status == "failed"]

    reason_codes = list(ticket_fact.get("reason_codes", []))
    if failed_checks:
        status = "failed"
        reason_codes.append("asset_checks_failed")
    elif ticket_fact.get("status") == "skipped":
        status = "skipped"
    elif any(outcome.status == "warning" for outcome in check_outcomes):
        status = "warning"
    else:
        status = "success"

    reason_codes.extend(lakehouse_state.get("reason_codes", []))
    reason_codes.extend(support_kpi_mart.get("reason_codes", []))
    reason_codes = sorted(set(reason_codes))
    report_path = settings.run_evidence_dir / f"{safe_file_stem(asset_key_to_str(RUN_EVIDENCE_KEY))}_{partition_key}.json"
    downstream_decision = build_downstream_decision(
        status=status,
        reason_codes=reason_codes,
        dry_run=bool(ticket_fact.get("dry_run", settings.ingest_dry_run)),
    )
    record = RunEvidence(
        evidence_schema_version="week06_run_evidence_v1",
        run_id=f"week06::{partition_key}",
        asset_key=asset_key_to_str(RUN_EVIDENCE_KEY),
        partition_key=partition_key,
        status=status,
        started_at=started_at,
        finished_at=utc_now_iso(),
        report_path=settings.relative_to_root(report_path),
        reason_codes=reason_codes,
        manifest_id=backfill_plan.get("upstream_manifest_id"),
        batch_id=ticket_fact.get("batch_id"),
        input_row_count=int(ticket_fact.get("input_row_count", 0)),
        output_row_count=int(ticket_fact.get("output_row_count", 0)),
        lakehouse_snapshot_id=lakehouse_state.get("lakehouse_snapshot_id"),
        dbt_invocation_id=support_kpi_mart.get("dbt_invocation_id"),
        semantic_metric_count=support_kpi_mart.get("semantic_metric_count"),
        data_release_id=settings.data_release_id,
        trace_id=settings.trace_id,
        git_sha=settings.git_sha,
        downstream_decision=downstream_decision,
        checks=check_payloads,
    )
    write_run_evidence(record, report_path, settings)
    summary_path = write_markdown_summary([record.to_dict()], settings.report_dir / "run_evidence_summary.md")

    payload = {
        **record.to_dict(),
        "checks_summary_path": checks_path,
        "markdown_summary_path": settings.relative_to_root(summary_path),
    }
    return Output(
        payload,
        metadata={
            "status": MetadataValue.text(status),
            "downstream_decision": MetadataValue.text(downstream_decision),
            "reason_codes": MetadataValue.json(reason_codes),
            "report_path": MetadataValue.path(str(report_path)),
        },
    )


@asset(
    key=DELIVERY_SUMMARY_KEY,
    ins={"run_evidence": AssetIn(key=RUN_EVIDENCE_KEY)},
    group_name=WEEK06_GROUP,
    partitions_def=WEEK06_PARTITIONS_DEF,
    description="Human-readable Week06 data factory delivery summary.",
    tags={"week": "06", "layer": "ops"},
)
def week06_data_factory_delivery_summary(
    context: AssetExecutionContext,
    run_evidence: dict,
) -> Output[dict]:
    settings = DataFactorySettings.from_env()
    partition_key = _partition_key(context, settings)
    path = settings.report_dir / "week06_delivery_summary.md"
    lines = [
        "# Week06 Delivery Summary",
        "",
        f"- partition_key: `{partition_key}`",
        f"- status: `{run_evidence.get('status')}`",
        f"- downstream_decision: `{run_evidence.get('downstream_decision')}`",
        f"- run_evidence: `{run_evidence.get('report_path')}`",
        f"- reason_codes: `{', '.join(run_evidence.get('reason_codes', []))}`",
        "",
        "## Boundary",
        "",
        "- Week03 ticket ingest logic is reused, not copied.",
        "- Week04 lakehouse and Week05 analytics are observation-only dependencies.",
        "- Default Week06 execution is dry-run and does not mutate PostgreSQL.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    payload = {
        "partition_key": partition_key,
        "status": run_evidence.get("status"),
        "downstream_decision": run_evidence.get("downstream_decision"),
        "report_path": settings.relative_to_root(path),
    }
    return Output(
        payload,
        metadata={
            "status": MetadataValue.text(str(payload["status"])),
            "report_path": MetadataValue.path(str(path)),
        },
    )


WEEK06_ASSETS = [
    week06_source_seed_manifests,
    week06_factory_manifest_gate,
    week06_raw_ticket_events_partitioned,
    week06_ticket_fact_partitioned,
    week06_lakehouse_state,
    week06_support_kpi_mart,
    week06_backfill_plan,
    week06_run_evidence_report,
    week06_data_factory_delivery_summary,
]

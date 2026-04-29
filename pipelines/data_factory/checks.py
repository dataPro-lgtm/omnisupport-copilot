"""Week06 asset checks.

The pure check functions are used by tests and by the run evidence asset. The
Dagster asset-check wrappers keep the UI path visible without copying ingest
business logic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from dagster import AssetCheckResult, asset_check

from pipelines.data_factory.asset_keys import RAW_TICKET_EVENTS_KEY
from pipelines.data_factory.backfill_plan import count_partition_rows, iter_jsonl
from pipelines.resources.config import DataFactorySettings


@dataclass(frozen=True)
class CheckOutcome:
    name: str
    status: str
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status in {"passed", "warning", "skipped"}

    def to_dict(self) -> dict:
        return asdict(self)


def check_manifest_consistency(settings: DataFactorySettings) -> CheckOutcome:
    manifests = [
        path for path in settings.manifest_dir.glob("*.json")
        if not path.name.startswith("source_manifest")
    ] if settings.manifest_dir.exists() else []
    structured_count = 0
    missing_assets = 0
    for path in manifests:
        import json

        data = json.loads(path.read_text())
        if data.get("modality") == "structured":
            structured_count += 1
        if not data.get("assets"):
            missing_assets += 1
    status = "passed" if structured_count >= 1 and missing_assets == 0 else "failed"
    reason_codes = [] if status == "passed" else ["structured_manifest_missing_or_empty"]
    return CheckOutcome(
        name="manifest_consistency",
        status=status,
        reason_codes=reason_codes,
        metadata={"manifest_count": len(manifests), "structured_manifest_count": structured_count},
    )


def check_row_count(ingest_stats: dict | None) -> CheckOutcome:
    stats = ingest_stats or {}
    total = int(stats.get("total", 0))
    valid = int(stats.get("valid", 0))
    status = "passed" if total > 0 and valid > 0 else "failed"
    return CheckOutcome(
        name="row_count_output_count",
        status=status,
        reason_codes=[] if status == "passed" else ["no_valid_input_rows"],
        metadata={"input_row_count": total, "valid_row_count": valid},
    )


def check_duplicate_idempotency(settings: DataFactorySettings) -> CheckOutcome:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in iter_jsonl(settings.ticket_seed_path):
        ticket_id = record.get("ticket_id")
        if not ticket_id:
            continue
        if ticket_id in seen:
            duplicates.add(ticket_id)
        seen.add(ticket_id)
    status = "passed" if not duplicates else "failed"
    return CheckOutcome(
        name="duplicate_idempotency",
        status=status,
        reason_codes=[] if status == "passed" else ["duplicate_ticket_id"],
        metadata={"duplicate_count": len(duplicates), "unique_ticket_count": len(seen)},
    )


def check_required_field_null_rate(settings: DataFactorySettings) -> CheckOutcome:
    required = ["ticket_id", "status", "priority", "product_line", "created_at"]
    records = list(iter_jsonl(settings.ticket_seed_path))
    nulls = {
        field_name: sum(1 for record in records if record.get(field_name) in (None, ""))
        for field_name in required
    }
    total_nulls = sum(nulls.values())
    status = "passed" if records and total_nulls == 0 else "failed"
    return CheckOutcome(
        name="required_field_null_rate",
        status=status,
        reason_codes=[] if status == "passed" else ["required_field_nulls_detected"],
        metadata={"row_count": len(records), "nulls": nulls},
    )


def check_partition_completeness(settings: DataFactorySettings, partition_key: str) -> CheckOutcome:
    partition_rows = count_partition_rows(settings.ticket_seed_path, partition_key)
    status = "passed" if partition_rows > 0 else "warning"
    return CheckOutcome(
        name="partition_completeness",
        status=status,
        reason_codes=[] if status == "passed" else ["partition_has_no_seed_rows"],
        metadata={"partition_key": partition_key, "partition_row_count": partition_rows},
    )


def run_week06_asset_checks(
    *,
    partition_key: str,
    settings: DataFactorySettings | None = None,
    ingest_stats: dict | None = None,
) -> list[CheckOutcome]:
    resolved = settings or DataFactorySettings.from_env()
    return [
        check_manifest_consistency(resolved),
        check_row_count(ingest_stats),
        check_duplicate_idempotency(resolved),
        check_required_field_null_rate(resolved),
        check_partition_completeness(resolved, partition_key),
    ]


def write_asset_checks_summary(outcomes: list[CheckOutcome], settings: DataFactorySettings) -> str:
    path = settings.report_dir / "asset_checks_summary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Week06 Asset Checks Summary",
        "",
        "| check | status | reason_codes |",
        "|---|---|---|",
    ]
    for outcome in outcomes:
        lines.append(
            f"| {outcome.name} | {outcome.status} | {', '.join(outcome.reason_codes)} |"
        )
    path.write_text("\n".join(lines) + "\n")
    return settings.relative_to_root(path)


@asset_check(asset=RAW_TICKET_EVENTS_KEY, name="manifest_consistency")
def manifest_consistency_check() -> AssetCheckResult:
    outcome = check_manifest_consistency(DataFactorySettings.from_env())
    return AssetCheckResult(passed=outcome.passed, metadata=outcome.metadata)


@asset_check(asset=RAW_TICKET_EVENTS_KEY, name="duplicate_idempotency")
def duplicate_idempotency_check() -> AssetCheckResult:
    outcome = check_duplicate_idempotency(DataFactorySettings.from_env())
    return AssetCheckResult(passed=outcome.passed, metadata=outcome.metadata)


@asset_check(asset=RAW_TICKET_EVENTS_KEY, name="required_field_null_rate")
def required_field_null_rate_check() -> AssetCheckResult:
    outcome = check_required_field_null_rate(DataFactorySettings.from_env())
    return AssetCheckResult(passed=outcome.passed, metadata=outcome.metadata)


@asset_check(asset=RAW_TICKET_EVENTS_KEY, name="partition_completeness")
def partition_completeness_check() -> AssetCheckResult:
    settings = DataFactorySettings.from_env()
    outcome = check_partition_completeness(settings, settings.default_partition)
    return AssetCheckResult(passed=outcome.passed, metadata=outcome.metadata)


@asset_check(asset=RAW_TICKET_EVENTS_KEY, name="row_count_output_count")
def row_count_output_count_check() -> AssetCheckResult:
    outcome = CheckOutcome(
        name="row_count_output_count",
        status="skipped",
        reason_codes=["requires_materialization_context"],
        metadata={},
    )
    return AssetCheckResult(passed=outcome.passed, metadata={"reason": "requires_materialization_context"})

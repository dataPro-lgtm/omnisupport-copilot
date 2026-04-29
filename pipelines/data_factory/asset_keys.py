"""Week06 Dagster asset key constants."""

from dagster import AssetKey

SEED_MANIFESTS_KEY = AssetKey(["week06", "source", "seed_manifests"])
MANIFEST_GATE_KEY = AssetKey(["week06", "factory", "manifest_gate"])
RAW_TICKET_EVENTS_KEY = AssetKey(["week06", "ingestion", "raw_ticket_events_partitioned"])
TICKET_FACT_KEY = AssetKey(["week06", "silver", "ticket_fact_partitioned"])
LAKEHOUSE_STATE_KEY = AssetKey(["week06", "external", "lakehouse_state"])
SUPPORT_KPI_MART_KEY = AssetKey(["week06", "external", "support_kpi_mart"])
BACKFILL_PLAN_KEY = AssetKey(["week06", "ops", "backfill_plan"])
RUN_EVIDENCE_KEY = AssetKey(["week06", "ops", "run_evidence_report"])
DELIVERY_SUMMARY_KEY = AssetKey(["week06", "ops", "data_factory_delivery_summary"])

WEEK06_ASSET_KEYS = [
    SEED_MANIFESTS_KEY,
    MANIFEST_GATE_KEY,
    RAW_TICKET_EVENTS_KEY,
    TICKET_FACT_KEY,
    LAKEHOUSE_STATE_KEY,
    SUPPORT_KPI_MART_KEY,
    BACKFILL_PLAN_KEY,
    RUN_EVIDENCE_KEY,
    DELIVERY_SUMMARY_KEY,
]


def asset_key_to_str(asset_key: AssetKey) -> str:
    return "/".join(asset_key.path)

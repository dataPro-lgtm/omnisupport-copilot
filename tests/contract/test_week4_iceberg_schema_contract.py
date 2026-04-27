from pathlib import Path

from pipelines.lakehouse.iceberg_schemas import BRONZE_SCHEMAS, SILVER_SCHEMAS
from pipelines.lakehouse.settings import LakehouseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_week4_settings_contract_has_required_env_keys():
    env_example = (PROJECT_ROOT / "infra" / "env" / ".env.example").read_text()
    required = [
        "ICEBERG_CATALOG_NAME",
        "ICEBERG_CATALOG_TYPE",
        "ICEBERG_CATALOG_URI",
        "ICEBERG_WAREHOUSE",
        "ICEBERG_NAMESPACE_BRONZE",
        "ICEBERG_NAMESPACE_SILVER",
        "ICEBERG_FILE_IO",
        "ICEBERG_S3_ENDPOINT",
        "ICEBERG_S3_ACCESS_KEY_ID",
        "ICEBERG_S3_SECRET_ACCESS_KEY",
        "WEEK04_DATA_RELEASE_ID",
        "WEEK04_INGEST_BATCH_ID",
        "WEEK04_REPORT_DIR",
    ]
    for key in required:
        assert key in env_example


def test_week4_core_schema_contracts_exist():
    assert "raw_ticket_event" in BRONZE_SCHEMAS
    assert "raw_doc_asset" in BRONZE_SCHEMAS
    assert "ticket_fact" in SILVER_SCHEMAS
    assert "knowledge_doc" in SILVER_SCHEMAS


def test_week4_core_tables_have_trace_and_time_fields():
    checks = {
        "raw_ticket_event": BRONZE_SCHEMAS["raw_ticket_event"],
        "raw_doc_asset": BRONZE_SCHEMAS["raw_doc_asset"],
        "ticket_fact": SILVER_SCHEMAS["ticket_fact"],
        "knowledge_doc": SILVER_SCHEMAS["knowledge_doc"],
    }
    for table_name, schema in checks.items():
        fields = {field[0] for field in schema["fields"]}
        assert fields & {"ingest_ts", "created_at", "indexed_at"}, table_name
        assert fields & {"ingest_batch_id", "data_release_id", "source_fingerprint"}, table_name


def test_week4_default_settings_validate():
    assert LakehouseSettings().validate() == []
    assert LakehouseSettings().warehouse_bucket == "omni-lakehouse"

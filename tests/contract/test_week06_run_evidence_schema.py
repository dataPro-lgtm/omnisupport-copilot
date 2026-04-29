import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "contracts" / "run_evidence" / "week06_run_evidence.schema.json"


def _example_payload(**overrides):
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "evidence_schema_version": "week06_run_evidence_v1",
        "run_id": "week06-pytest-001",
        "asset_key": "week06/ops/run_evidence_report",
        "partition_key": "2026-04-17",
        "status": "success",
        "started_at": now,
        "finished_at": now,
        "report_path": "reports/week06/run_evidence/week06-pytest-001.json",
        "reason_codes": [],
        "manifest_id": "manifest-tickets-synthetic-20260331-001",
        "batch_id": "batch-20260331-001",
        "input_row_count": 10,
        "output_row_count": 10,
        "downstream_decision": "proceed_to_week07",
        "checks": [
            {
                "name": "manifest_consistency",
                "status": "passed",
                "reason_codes": [],
                "metadata": {"manifest_count": 1},
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_week06_run_evidence_schema_is_valid_json_schema():
    schema = json.loads(SCHEMA_PATH.read_text())
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)


def test_week06_run_evidence_accepts_success_payload():
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(_example_payload(), schema)


def test_week06_run_evidence_accepts_optional_dependency_not_available():
    schema = json.loads(SCHEMA_PATH.read_text())
    payload = _example_payload(
        asset_key="week06/external/lakehouse_state",
        status="not_available",
        reason_codes=["week04_lakehouse_not_available"],
        output_row_count=0,
        lakehouse_snapshot_id=None,
        downstream_decision="dry_run_only",
    )

    jsonschema.validate(payload, schema)


def test_week06_run_evidence_rejects_non_week06_asset_key():
    schema = json.loads(SCHEMA_PATH.read_text())
    payload = _example_payload(asset_key="week05/ops/run_evidence_report")
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)

    errors = list(validator.iter_errors(payload))

    assert errors

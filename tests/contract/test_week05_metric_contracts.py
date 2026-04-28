import json
from pathlib import Path

import jsonschema

PROJECT_ROOT = Path(__file__).parent.parent.parent
TOOL_CONTRACT = PROJECT_ROOT / "contracts" / "tools" / "tools" / "query_support_kpis_v1.json"
TOOL_CONTRACT_SCHEMA = PROJECT_ROOT / "contracts" / "tools" / "tool_contract_schema.json"


def test_query_support_kpis_contract_matches_tool_schema():
    tool = json.loads(TOOL_CONTRACT.read_text())
    schema = json.loads(TOOL_CONTRACT_SCHEMA.read_text())

    jsonschema.validate(tool, schema)
    assert tool["name"] == "query_support_kpis_v1"
    assert tool["idempotent"] is True
    assert "METRIC_DENIED" in tool["failure_codes"]
    assert "raw_sql" not in tool["input_schema"]["properties"]


def test_query_support_kpis_contract_rejects_extra_raw_sql_field():
    tool = json.loads(TOOL_CONTRACT.read_text())
    payload = {
        "actor_role": "instructor",
        "metrics": ["ticket_count"],
        "date_from": "2026-04-01",
        "date_to": "2026-04-30",
        "raw_sql": "select * from ticket_fact",
    }

    validator_cls = jsonschema.validators.validator_for(tool["input_schema"])
    validator_cls.check_schema(tool["input_schema"])
    validator = validator_cls(tool["input_schema"])
    errors = list(validator.iter_errors(payload))

    assert errors

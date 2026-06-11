import json
from pathlib import Path

import jsonschema
import pytest


PROJECT_ROOT = Path(__file__).parent.parent.parent
CONTRACT_DIR = PROJECT_ROOT / "contracts" / "data"
FIXTURE_DIR = PROJECT_ROOT / "tests" / "contract" / "fixtures" / "week07"


SCHEMA_FIXTURES = [
    ("knowledge_section.schema.json", "knowledge_section.valid.json"),
    ("document_chunk.schema.json", "document_chunk.valid.json"),
    ("evidence_anchor.schema.json", "evidence_anchor.valid.json"),
    ("parse_run.schema.json", "parse_run.valid.json"),
    ("chunk_quality_sample.schema.json", "chunk_quality_sample.valid.json"),
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.mark.parametrize("schema_name,_fixture_name", SCHEMA_FIXTURES)
def test_week07_schema_is_valid_json_schema(schema_name: str, _fixture_name: str):
    schema = _load_json(CONTRACT_DIR / schema_name)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)


@pytest.mark.parametrize("schema_name,fixture_name", SCHEMA_FIXTURES)
def test_week07_fixture_validates(schema_name: str, fixture_name: str):
    schema = _load_json(CONTRACT_DIR / schema_name)
    fixture = _load_json(FIXTURE_DIR / fixture_name)

    jsonschema.validate(fixture, schema)


def test_document_chunk_requires_at_least_one_evidence_anchor():
    schema = _load_json(CONTRACT_DIR / "document_chunk.schema.json")
    fixture = _load_json(FIXTURE_DIR / "document_chunk.missing_anchor.invalid.json")
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)

    errors = list(validator.iter_errors(fixture))

    assert errors


def test_pdf_evidence_anchor_requires_page_number():
    schema = _load_json(CONTRACT_DIR / "evidence_anchor.schema.json")
    fixture = _load_json(FIXTURE_DIR / "evidence_anchor.pdf_missing_page.invalid.json")
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)

    errors = list(validator.iter_errors(fixture))

    assert errors

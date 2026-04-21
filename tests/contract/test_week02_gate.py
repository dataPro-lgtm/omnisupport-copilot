"""Week02 contract + manifest gate tests.

These tests turn the Week02 lecture artifacts into executable checks:
- four modality fixtures must validate against the current JSON contracts
- the practice manifest must validate and produce accept/warn/quarantine judgments
- incremental manifests missing cursor metadata must be rejected early
"""

import importlib
import json
import sys
from pathlib import Path

import jsonschema
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

seed_loader = importlib.import_module("pipelines.ingestion.seed_loader")
ManifestValidator = seed_loader.ManifestValidator
SeedLoader = seed_loader.SeedLoader

CONTRACTS_DIR = PROJECT_ROOT / "contracts" / "data"
FIXTURE_PATH = PROJECT_ROOT / "tests" / "contract" / "fixtures" / "week02" / "sample_records.json"
MANIFEST_SCHEMA_PATH = PROJECT_ROOT / "data" / "seed_manifests" / "source_manifest_schema.json"
PRACTICE_MANIFEST_PATH = PROJECT_ROOT / "data" / "seed_manifests" / "manifest_week02_practice_v1.json"
WEEK01_MANIFEST_PATHS = [
    PROJECT_ROOT / "data" / "seed_manifests" / "manifest_edge_gateway_pdf_v1.json",
    PROJECT_ROOT / "data" / "seed_manifests" / "manifest_tickets_synthetic_v1.json",
    PROJECT_ROOT / "data" / "seed_manifests" / "manifest_workspace_helpcenter_v1.json",
]

CONTRACT_PATHS = {
    "ticket": CONTRACTS_DIR / "ticket_contract.json",
    "document": CONTRACTS_DIR / "doc_asset_contract.json",
    "audio": CONTRACTS_DIR / "audio_asset_contract.json",
    "video": CONTRACTS_DIR / "video_asset_contract.json",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def week02_samples() -> dict:
    return load_json(FIXTURE_PATH)


@pytest.mark.parametrize("record_key", ["ticket", "document", "audio", "video"])
def test_week02_valid_fixture_records_pass_current_contracts(week02_samples: dict, record_key: str):
    schema = load_json(CONTRACT_PATHS[record_key])
    record = week02_samples["valid_records"][record_key]
    jsonschema.validate(record, schema)


@pytest.mark.parametrize(
    ("case_name", "expected_contract"),
    [
        ("ticket_missing_priority", "ticket"),
        ("document_bad_fingerprint", "document"),
        ("audio_missing_pii_redacted", "audio"),
        ("video_bad_enum", "video"),
    ],
)
def test_week02_invalid_fixture_records_fail_contracts(
    week02_samples: dict,
    case_name: str,
    expected_contract: str,
):
    schema = load_json(CONTRACT_PATHS[expected_contract])
    record = week02_samples["invalid_records"][case_name]["record"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema)


def test_week02_practice_manifest_validates_against_schema():
    manifest = load_json(PRACTICE_MANIFEST_PATH)
    schema = load_json(MANIFEST_SCHEMA_PATH)
    jsonschema.validate(manifest, schema)


def test_week02_manifest_validator_rejects_incremental_cursor_without_cursor_field():
    manifest = load_json(PRACTICE_MANIFEST_PATH)
    manifest["selection_window"].pop("cursor_field")
    errors = ManifestValidator().validate(manifest)
    assert any("selection_window.cursor_field" in error for error in errors)


def test_week02_seed_loader_emits_gate_judgments_and_report(tmp_path: Path):
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    manifest_dir.joinpath(PRACTICE_MANIFEST_PATH.name).write_text(PRACTICE_MANIFEST_PATH.read_text())
    report_path = tmp_path / "reports" / "week02-dry-run.json"

    loader = SeedLoader(
        manifest_dir=manifest_dir,
        batch_id="batch-test-week02-001",
        dry_run=True,
        report_path=report_path,
    )

    results = loader.run()

    assert not loader.rejected_manifests
    assert len(results) == 1

    result = results[0]
    judgments = {entry.source_id: entry.gate_judgment for entry in result.run_evidence}

    assert result.accepted_count == 1
    assert result.warn_count == 1
    assert result.quarantine_count == 1
    assert result.fail_count == 0
    assert judgments["structured:tickets:practice_ok"] == "accept"
    assert judgments["structured:tickets:practice_warn"] == "warn"
    assert judgments["structured:tickets:practice_quarantine"] == "quarantine"

    report = load_json(report_path)
    assert report["summary"]["accepted_count"] == 1
    assert report["summary"]["warn_count"] == 1
    assert report["summary"]["quarantine_count"] == 1
    assert report["summary"]["reject_count"] == 0


def test_seed_loader_can_limit_run_to_explicit_manifest_paths():
    loader = SeedLoader(
        manifest_dir=PROJECT_ROOT / "data" / "seed_manifests",
        manifest_paths=WEEK01_MANIFEST_PATHS,
        batch_id="batch-test-week01-001",
        dry_run=True,
    )

    results = loader.run()

    assert not loader.rejected_manifests
    assert len(results) == 3
    assert {result.manifest_id for result in results} == {
        "manifest-edge-gateway-pdf-20260331-001",
        "manifest-tickets-synthetic-20260331-001",
        "manifest-workspace-helpcenter-20260331-001",
    }
    assert all(result.warn_count == 0 for result in results)
    assert all(result.quarantine_count == 0 for result in results)
    assert all(result.fail_count == 0 for result in results)

"""Contract Tests — JSON Schema 结构校验

这些测试验证所有 JSON Schema 契约文件的结构完整性和示例数据合法性。
Week01 DoD：所有契约测试必须通过。
"""

import json
from pathlib import Path

import jsonschema
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONTRACTS_DIR = PROJECT_ROOT / "contracts"


# ── Schema 文件加载 ───────────────────────────────────────────────────────────

def load_schema(path: Path) -> dict:
    return json.loads(path.read_text())


# ── 工具契约文件路径 ──────────────────────────────────────────────────────────

TOOL_CONTRACTS = [
    CONTRACTS_DIR / "tools" / "tools" / "search_knowledge.json",
    CONTRACTS_DIR / "tools" / "tools" / "get_ticket_status.json",
    CONTRACTS_DIR / "tools" / "tools" / "create_ticket.json",
]

DATA_CONTRACTS = [
    CONTRACTS_DIR / "data" / "doc_asset_contract.json",
    CONTRACTS_DIR / "data" / "ticket_contract.json",
    CONTRACTS_DIR / "data" / "audio_asset_contract.json",
    CONTRACTS_DIR / "data" / "video_asset_contract.json",
]


# ── 测试：契约文件存在 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("schema_path", DATA_CONTRACTS + TOOL_CONTRACTS + [
    CONTRACTS_DIR / "tools" / "tool_contract_schema.json",
    CONTRACTS_DIR / "release" / "release_manifest_schema.json",
])
def test_contract_file_exists(schema_path: Path):
    assert schema_path.exists(), f"Contract file missing: {schema_path}"


# ── 测试：数据契约是合法的 JSON ───────────────────────────────────────────────

@pytest.mark.parametrize("schema_path", DATA_CONTRACTS)
def test_data_contract_is_valid_json(schema_path: Path):
    schema = load_schema(schema_path)
    assert isinstance(schema, dict)
    assert "type" in schema or "$ref" in schema


# ── 测试：工单契约必含字段 ────────────────────────────────────────────────────

def test_ticket_contract_required_fields():
    schema = load_schema(CONTRACTS_DIR / "data" / "ticket_contract.json")
    required = schema.get("required", [])

    must_have = ["ticket_id", "status", "priority", "product_line", "pii_level", "quality_gate"]
    for field in must_have:
        assert field in required, f"Required field missing from ticket contract: {field}"


# ── 测试：工具契约必含字段 ────────────────────────────────────────────────────

@pytest.mark.parametrize("tool_path", TOOL_CONTRACTS)
def test_tool_contract_required_fields(tool_path: Path):
    tool = load_schema(tool_path)

    must_have = ["name", "version", "allowed_roles", "audit_fields", "failure_codes", "hitl_conditions"]
    for field in must_have:
        assert field in tool, f"Tool contract '{tool_path.name}' missing field: {field}"


# ── 测试：审计字段完整 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("tool_path", TOOL_CONTRACTS)
def test_tool_audit_fields_complete(tool_path: Path):
    tool = load_schema(tool_path)
    audit = tool.get("audit_fields", {})
    assert "log_input" in audit
    assert "log_output" in audit
    assert "log_actor" in audit
    assert "retention_days" in audit
    assert isinstance(audit["retention_days"], int)
    assert audit["retention_days"] >= 1


# ── 测试：release manifest 示例合法 ──────────────────────────────────────────

def test_release_manifest_example_valid():
    schema = load_schema(CONTRACTS_DIR / "release" / "release_manifest_schema.json")
    example = load_schema(CONTRACTS_DIR / "release" / "release_manifest_example.json")

    # 必须字段检查
    schema_required = schema.get("required", [])
    for field in schema_required:
        assert field in example, f"Release manifest example missing required field: {field}"


# ── 测试：seed manifest 结构 ──────────────────────────────────────────────────

def test_seed_manifests_structure():
    manifest_dir = PROJECT_ROOT / "data" / "seed_manifests"
    manifests = [f for f in manifest_dir.glob("*.json") if not f.name.startswith("source_manifest")]

    assert len(manifests) >= 1, "At least one seed manifest required"

    for manifest_path in manifests:
        manifest = load_schema(manifest_path)
        assert "manifest_id" in manifest, f"{manifest_path.name}: missing manifest_id"
        assert "modality" in manifest, f"{manifest_path.name}: missing modality"
        assert "assets" in manifest, f"{manifest_path.name}: missing assets"
        assert len(manifest["assets"]) >= 1, f"{manifest_path.name}: assets list is empty"


def test_seed_manifests_validate_against_schema():
    manifest_dir = PROJECT_ROOT / "data" / "seed_manifests"
    schema = load_schema(manifest_dir / "source_manifest_schema.json")
    manifests = [f for f in manifest_dir.glob("*.json") if not f.name.startswith("source_manifest")]

    for manifest_path in manifests:
        manifest = load_schema(manifest_path)
        jsonschema.validate(manifest, schema)

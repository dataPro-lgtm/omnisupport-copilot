import json
from pathlib import Path
import sys

import jsonschema
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.parse_normalize.models import sha256_bytes
from pipelines.parse_normalize.run_parse import run_parse_pipeline


def _write_manifest(tmp_path: Path, source_path: Path, checksum: str) -> Path:
    manifest = {
        "manifest_id": "manifest-week07-pytest-20260424-001",
        "schema_version": "source_manifest_v1",
        "batch_id": "batch-20260424-001",
        "modality": "document",
        "source_type": "help_center",
        "product_line": "northstar_workspace",
        "license_tag": "course_synthetic",
        "contract_ref": "omni://contracts/data/doc_asset/v1",
        "load_mode": "full_snapshot",
        "assets": [
            {
                "source_id": "doc:workspace:pytest001",
                "source_url_or_path": str(source_path),
                "asset_type": "html",
                "size_bytes": source_path.stat().st_size,
                "checksum_sha256": checksum,
                "metadata_status": "complete",
                "pii_scan_status": "clear",
                "notes": "Pytest help center document",
            }
        ],
        "ingest_config": {
            "parser": "unstructured",
            "chunk_size": 160,
            "chunk_overlap": 20,
            "pii_scan": True,
        },
        "created_at": "2026-04-24T00:00:00Z",
        "owner": "pytest",
    }
    path = tmp_path / "manifest_week07_pytest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_week07_parse_pipeline_dry_run_outputs_artifacts(tmp_path: Path):
    html = tmp_path / "help.html"
    html.write_text(
        """
        <html><body>
          <h1>Workspace Recovery</h1>
          <p>Admins can restore workspace access by validating identity and replaying recovery steps.</p>
          <p>Every recovery answer must cite source evidence and preserve release lineage.</p>
        </body></html>
        """,
        encoding="utf-8",
    )
    checksum = sha256_bytes(html.read_bytes())
    manifest_path = _write_manifest(tmp_path, html, checksum)

    parse_run, gate = run_parse_pipeline(
        manifest_path=manifest_path,
        parser="fallback",
        data_release_id="week07-pytest",
        dry_run=True,
        artifacts_dir=tmp_path / "artifacts",
        report_json=tmp_path / "reports" / "parse_run_report.json",
        quality_report_md=tmp_path / "reports" / "chunk_quality_report.md",
        week8_gate_json=tmp_path / "reports" / "week8_ready_gate.json",
    )

    assert parse_run.section_count >= 1
    assert parse_run.chunk_count >= 1
    assert parse_run.anchor_count == parse_run.chunk_count
    assert gate.week8_ready is True

    chunks = json.loads((tmp_path / "artifacts" / "chunks.json").read_text())
    anchors = json.loads((tmp_path / "artifacts" / "evidence_anchors.json").read_text())
    chunk_schema = json.loads((PROJECT_ROOT / "contracts/data/document_chunk.schema.json").read_text())
    anchor_schema = json.loads((PROJECT_ROOT / "contracts/data/evidence_anchor.schema.json").read_text())
    jsonschema.validate(chunks[0], chunk_schema)
    jsonschema.validate(anchors[0], anchor_schema)
    assert chunks[0]["allowed_for_indexing"] is True


def test_week07_expected_fingerprint_mismatch_fails(tmp_path: Path):
    html = tmp_path / "help.html"
    html.write_text("<h1>Mismatch</h1><p>Wrong fingerprint should fail.</p>", encoding="utf-8")
    manifest_path = _write_manifest(tmp_path, html, sha256_bytes(html.read_bytes()))

    with pytest.raises(ValueError, match="source_fingerprint mismatch"):
        run_parse_pipeline(
            manifest_path=manifest_path,
            parser="fallback",
            expected_fingerprint="0" * 64,
            dry_run=True,
            artifacts_dir=tmp_path / "artifacts",
            report_json=None,
            quality_report_md=None,
            week8_gate_json=None,
        )

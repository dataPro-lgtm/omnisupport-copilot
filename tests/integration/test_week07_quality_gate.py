from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.parse_normalize.models import DocumentChunk, EvidenceAnchor, ParsedSection
from pipelines.parse_normalize.quality_gate import evaluate_quality_gate


def _section() -> ParsedSection:
    return ParsedSection(
        section_id="section-0123456789abcdef",
        doc_id="doc-1",
        source_id="doc:workspace:pytest001",
        source_fingerprint="a" * 64,
        asset_type="html",
        section_index=0,
        section_path="Workspace Recovery",
        section_type="text",
        content="Recovery steps require cited evidence.",
        page_no=None,
        bbox=None,
        bbox_missing_reason=None,
        parser_backend="fallback",
        parser_capability={
            "preserves_page": False,
            "preserves_bbox": False,
            "preserves_table": False,
            "fallback_used": True,
            "warnings": ["fallback_parser_used"],
        },
        parse_strategy_version="parse_normalize_v1",
        data_release_id="week07-pytest",
        doc_version="pytest",
        source_url_or_path="file:///tmp/help.html",
        metadata={"raw_available": True},
    )


def _chunk() -> DocumentChunk:
    return DocumentChunk(
        chunk_id="chunk-0123456789abcdef",
        doc_id="doc-1",
        source_id="doc:workspace:pytest001",
        section_id="section-0123456789abcdef",
        source_fingerprint="a" * 64,
        chunk_index=0,
        section_chunk_index=0,
        chunk_strategy_version="section_aware_v1",
        parse_strategy_version="parse_normalize_v1",
        data_release_id="week07-pytest",
        doc_version="pytest",
        section_path="Workspace Recovery",
        section_type="text",
        content="Recovery steps require cited evidence.",
        page_no=None,
        bbox=None,
        reason_codes=["fallback_parser_used"],
    )


def test_week07_quality_gate_rejects_unanchored_chunk():
    section = _section()
    chunk = _chunk()

    gate = evaluate_quality_gate([section], [chunk], [])

    assert gate.quality_status == "fail"
    assert gate.week8_ready is False
    assert "missing_evidence_anchor" in gate.errors


def test_week07_quality_gate_warns_on_fallback_but_allows_real_local_source():
    section = _section()
    chunk = _chunk()
    anchor = EvidenceAnchor(
        anchor_id="anchor-0123456789abcdef",
        chunk_id=chunk.chunk_id,
        section_id=section.section_id,
        doc_id=section.doc_id,
        source_id=section.source_id,
        source_fingerprint=section.source_fingerprint,
        asset_type=section.asset_type,
        anchor_type="fallback",
        source_url_or_path=section.source_url_or_path or "",
        section_path=section.section_path,
        doc_version=section.doc_version,
        page_no=None,
        bbox=None,
        bbox_missing_reason=None,
        parser_backend="fallback",
        parser_capability=section.parser_capability,
        data_release_id="week07-pytest",
        created_at="2026-04-24T00:00:00+00:00",
    )
    chunk.evidence_anchor_ids = [anchor.anchor_id]
    chunk.anchor_count = 1

    gate = evaluate_quality_gate([section], [chunk], [anchor])

    assert gate.quality_status == "warn"
    assert gate.week8_ready is True
    assert chunk.allowed_for_indexing is True

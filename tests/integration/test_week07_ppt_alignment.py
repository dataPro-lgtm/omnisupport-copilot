import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.chunker.code_ast import split_code_symbols
from pipelines.chunker.contextual import build_context_prefix
from pipelines.chunker.late_chunking import plan_late_chunking
from pipelines.chunker.structure_aware import split_section_text
from pipelines.incremental.update import decide_incremental_update
from pipelines.multimodal.clip_embed import clip_embedding_plan
from pipelines.parse.pdf_typer import detect_pdf_type
from pipelines.parse.table_extractor import choose_table_strategy
from pipelines.parse_normalize.run_parse import run_parse_pipeline
from pipelines.quality.report import build_quality_report


def test_week07_pdf_auto_uses_idp_route_with_baseline_fallback(tmp_path: Path):
    manifest_path = PROJECT_ROOT / "data/seed_manifests/manifest_week07_multimodal_v1.json"
    assert manifest_path.exists(), "Run scripts/week07/generate_multimodal_fixtures.py first."

    parse_run, gate = run_parse_pipeline(
        manifest_path=manifest_path,
        parser="auto",
        data_release_id="week07-ppt-alignment-pytest",
        dry_run=True,
        artifacts_dir=tmp_path / "artifacts",
        report_json=tmp_path / "reports" / "parse_run_report.json",
        quality_report_md=tmp_path / "reports" / "chunk_quality_report.md",
        week8_gate_json=tmp_path / "reports" / "week8_ready_gate.json",
    )

    sections = json.loads((tmp_path / "artifacts" / "sections.json").read_text())
    chunks = json.loads((tmp_path / "artifacts" / "chunks.json").read_text())
    anchors = json.loads((tmp_path / "artifacts" / "evidence_anchors.json").read_text())
    pdf_sections = [section for section in sections if section["asset_type"] == "pdf"]

    assert parse_run.errors == []
    assert gate.metrics["gate_decision"] in {"pass", "warn"}
    assert pdf_sections
    assert pdf_sections[0]["parser_backend"] in {"marker", "docling", "pypdf_baseline"}
    assert "span_start" in chunks[0]
    assert "context_prefix" in chunks[0]
    assert "heading_path" in anchors[0]


def test_week07_ppt_alignment_helper_modules_are_deterministic():
    slices = split_section_text(
        "Title\n\nFirst sentence. Second sentence. Third sentence.",
        section_path="Guide / Recovery",
        chunk_size=24,
        overlap=4,
    )
    assert slices
    assert slices[0].span_start >= 0
    assert slices[0].heading_path == ["Guide", "Recovery"]

    prefix = build_context_prefix(doc_title="Help Center", heading_path=slices[0].heading_path)
    assert "Help Center" in prefix
    assert plan_late_chunking(len(slices)).enabled is False
    assert split_code_symbols("def recover():\n    return True\n")[0].symbol_name == "recover"
    assert choose_table_strategy(12).strategy == "markdown_chunk"
    assert choose_table_strategy(400, has_business_keys=True).strategy == "sql_table"
    assert decide_incremental_update("a", "a").action == "skip"
    assert clip_embedding_plan().reason in {"ready", "optional_sentence_transformers_not_installed"}


def test_week07_pdf_type_detector_reports_route_for_fixture():
    pdf_path = PROJECT_ROOT / "data/week07_media/workspace_recovery_manual.pdf"
    report = detect_pdf_type(path=pdf_path)

    assert report.page_count >= 1
    assert report.pdf_type in {"text_based", "hybrid", "scanned", "unknown"}
    assert report.recommended_route in {
        "marker_or_docling",
        "idp_plus_ocr_fallback",
        "mistral_ocr_or_ocr_idp",
        "manual_review",
    }


def test_week07_quality_report_projects_gate_dimensions(tmp_path: Path):
    manifest_path = PROJECT_ROOT / "data/seed_manifests/manifest_week07_multimodal_v1.json"
    _, gate = run_parse_pipeline(
        manifest_path=manifest_path,
        parser="auto",
        data_release_id="week07-quality-report-pytest",
        dry_run=True,
        artifacts_dir=tmp_path / "artifacts",
        report_json=None,
        quality_report_md=None,
        week8_gate_json=None,
    )

    report = build_quality_report(gate)
    assert 0.0 <= report.completeness_score <= 1.0
    assert 0.0 <= report.noise_score <= 1.0
    assert 0.0 <= report.evidence_score <= 1.0
    assert report.gate_decision in {"pass", "warn", "block"}

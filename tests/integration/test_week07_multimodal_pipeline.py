import json
from pathlib import Path
import sys
import wave


PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.parse_normalize.run_parse import run_parse_pipeline


def test_week07_multimodal_manifest_parses_real_media(tmp_path: Path):
    manifest_path = PROJECT_ROOT / "data/seed_manifests/manifest_week07_multimodal_v1.json"
    assert manifest_path.exists(), "Run scripts/week07/generate_multimodal_fixtures.py first."

    parse_run, gate = run_parse_pipeline(
        manifest_path=manifest_path,
        parser="auto",
        data_release_id="week07-multimodal-pytest",
        dry_run=True,
        artifacts_dir=tmp_path / "artifacts",
        report_json=tmp_path / "reports" / "parse_run_report.json",
        quality_report_md=tmp_path / "reports" / "chunk_quality_report.md",
        week8_gate_json=tmp_path / "reports" / "week8_ready_gate.json",
    )

    assert parse_run.source_count == 4
    assert parse_run.chunk_count >= 7
    assert parse_run.anchor_count == parse_run.chunk_count
    assert parse_run.errors == []
    assert gate.week8_ready is True

    sections = json.loads((tmp_path / "artifacts" / "sections.json").read_text())
    anchors = json.loads((tmp_path / "artifacts" / "evidence_anchors.json").read_text())

    assert {section["asset_type"] for section in sections} == {"pdf", "image", "audio", "video"}
    assert any(
        section["asset_type"] == "pdf"
        and section["parser_backend"] in {"marker", "docling", "pypdf_baseline", "pypdf"}
        for section in sections
    )
    assert "audio_transcript_sidecar" in {section["parser_backend"] for section in sections}
    assert "video_ffmpeg_sidecar" in {section["parser_backend"] for section in sections}
    assert any(section["parser_backend"] in {"tesseract_ocr", "ocr_sidecar"} for section in sections)
    assert any("identity validation" in section["content"].lower() for section in sections)
    assert any(anchor["anchor_type"] == "timestamp" for anchor in anchors)
    assert any(anchor["asset_type"] == "video" and anchor.get("metadata", {}).get("media") for anchor in anchors)


def test_week07_audio_without_transcript_does_not_index_binary_garbage(tmp_path: Path):
    audio_path = tmp_path / "no_transcript.wav"
    with wave.open(str(audio_path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 800)

    parse_run, gate = run_parse_pipeline(
        manifest_path=None,
        input_path=audio_path,
        source_id="audio:week07:no-transcript",
        content_type="audio",
        parser="auto",
        data_release_id="week07-audio-no-transcript",
        dry_run=True,
        artifacts_dir=tmp_path / "artifacts",
        report_json=tmp_path / "reports" / "parse_run_report.json",
        quality_report_md=tmp_path / "reports" / "chunk_quality_report.md",
        week8_gate_json=tmp_path / "reports" / "week8_ready_gate.json",
    )

    assert parse_run.status == "failed"
    assert gate.week8_ready is False
    assert "no_chunks" in parse_run.errors
    chunks = json.loads((tmp_path / "artifacts" / "chunks.json").read_text())
    assert chunks == []

"""Generate small real Week07 multimodal fixtures.

The fixtures are course-synthetic but real files:
- PDF with extractable text.
- PNG with visible text for OCR.
- WAV course-synthetic audio bytes.
- MP4 with visible frame text generated through imageio-ffmpeg.

Run from the repository root:
    python scripts/week07/generate_multimodal_fixtures.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import wave


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEDIA_DIR = PROJECT_ROOT / "data" / "week07_media"
MANIFEST_PATH = PROJECT_ROOT / "data" / "seed_manifests" / "manifest_week07_multimodal_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_pdf(path: Path) -> None:
    lines = [
        "OmniSupport Week07 PDF Manual",
        "Workspace recovery requires identity validation before replay.",
        "Every answer must cite page evidence and preserve release lineage.",
        "Escalation policy: missing evidence blocks Week08 indexing.",
    ]
    text_ops = ["BT /F1 18 Tf 72 720 Td 24 TL"]
    for line in lines:
        text_ops.append(f"({_pdf_escape(line)}) Tj T*")
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("utf-8")

    objects: list[bytes] = []

    def obj(number: int, body: str | bytes) -> bytes:
        payload = body if isinstance(body, bytes) else body.encode("utf-8")
        return f"{number} 0 obj\n".encode("utf-8") + payload + b"\nendobj\n"

    objects.append(obj(1, "<< /Type /Catalog /Pages 2 0 R >>"))
    objects.append(obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"))
    objects.append(
        obj(
            3,
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        )
    )
    objects.append(
        obj(4, b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    )
    objects.append(obj(5, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))

    output = b"%PDF-1.4\n"
    offsets = [0]
    for item in objects:
        offsets.append(len(output))
        output += item
    xref_pos = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets[1:]:
        output += f"{offset:010d} 00000 n \n".encode("ascii")
    output += (
        f"trailer\n<< /Root 1 0 R /Size {len(objects) + 1} >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    path.write_bytes(output)


def _write_image(path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1100, 520), color=(248, 250, 252))
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if Path(font_path).exists():
        font_title = ImageFont.truetype(font_path, 48)
        font_body = ImageFont.truetype(font_path, 34)
    else:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
    draw.rectangle((30, 30, 1070, 490), outline=(20, 80, 120), width=4)
    draw.text((70, 80), "Week07 OCR Evidence Card", fill=(15, 23, 42), font=font_title)
    draw.text((70, 170), "Recover workspace only after identity check.", fill=(15, 23, 42), font=font_body)
    draw.text((70, 240), "Citations must point to source evidence.", fill=(15, 23, 42), font=font_body)
    draw.text((70, 310), "Release lineage: week07-multimodal-demo.", fill=(15, 23, 42), font=font_body)
    image.save(path)


def _write_fallback_wav(path: Path) -> None:
    sample_rate = 16_000
    duration_sec = 3
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        frames = bytearray()
        for index in range(sample_rate * duration_sec):
            # Deterministic two-tone classroom placeholder if espeak-ng is unavailable.
            value = 4000 if (index // 800) % 2 else -4000
            frames.extend(struct.pack("<h", value))
        audio.writeframes(bytes(frames))


def _write_audio(path: Path) -> None:
    speech = (
        "Workspace recovery call. The customer cannot access the dashboard. "
        "The agent validates identity, replays recovery steps, and records citation evidence."
    )
    if shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-w", str(path), "-s", "140", speech], check=True)
    else:
        _write_fallback_wav(path)


def _write_video(path: Path, audio_path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont
    import imageio_ffmpeg

    _ = audio_path  # Kept for manifest lineage; classroom video uses transcript sidecar.
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 46) if Path(font_path).exists() else ImageFont.load_default()
    small_font = ImageFont.truetype(font_path, 34) if Path(font_path).exists() else ImageFont.load_default()
    frame = Image.new("RGB", (1280, 720), color=(11, 32, 51))
    draw = ImageDraw.Draw(frame)
    draw.text((70, 90), "Week07 Video Evidence", fill=(255, 255, 255), font=font)
    draw.text((70, 190), "Step 1: validate identity", fill=(255, 255, 255), font=small_font)
    draw.text((70, 260), "Step 2: replay recovery steps", fill=(255, 255, 255), font=small_font)
    draw.text((70, 330), "Step 3: cite evidence anchors", fill=(255, 255, 255), font=small_font)

    writer = imageio_ffmpeg.write_frames(
        str(path),
        size=frame.size,
        fps=1,
        codec="libx264",
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
    )
    writer.send(None)
    try:
        for _index in range(5):
            writer.send(frame.tobytes())
    finally:
        writer.close()


def main() -> None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = MEDIA_DIR / "workspace_recovery_manual.pdf"
    image_path = MEDIA_DIR / "workspace_recovery_evidence.png"
    audio_path = MEDIA_DIR / "support_call_recovery.wav"
    video_path = MEDIA_DIR / "workspace_recovery_demo.mp4"
    audio_transcript_path = MEDIA_DIR / "support_call_recovery.transcript.jsonl"
    video_transcript_path = MEDIA_DIR / "workspace_recovery_demo.transcript.jsonl"
    image_ocr_path = MEDIA_DIR / "workspace_recovery_evidence.ocr.txt"
    keyframe_ocr_path = MEDIA_DIR / "workspace_recovery_demo.keyframe_ocr.txt"

    _write_pdf(pdf_path)
    _write_image(image_path)
    _write_audio(audio_path)
    _write_video(video_path, audio_path)

    audio_rows = [
        {
            "start_ts": 0.0,
            "end_ts": 2.4,
            "speaker": "customer",
            "text": "The customer cannot access the workspace dashboard after a password reset.",
        },
        {
            "start_ts": 2.4,
            "end_ts": 5.0,
            "speaker": "agent",
            "text": "The agent validates identity, replays recovery steps, and records citation evidence.",
        },
    ]
    video_rows = [
        {
            "start_ts": 0.0,
            "end_ts": 2.5,
            "speaker": "narrator",
            "text": "The video demonstrates identity validation before workspace recovery.",
        },
        {
            "start_ts": 2.5,
            "end_ts": 5.0,
            "speaker": "narrator",
            "text": "The final step is to cite evidence anchors before Week08 indexing.",
        },
    ]
    _write_jsonl(audio_transcript_path, audio_rows)
    _write_jsonl(video_transcript_path, video_rows)
    image_ocr_path.write_text(
        "Week07 OCR Evidence Card\n"
        "Recover workspace only after identity check.\n"
        "Citations must point to source evidence.\n"
        "Release lineage: week07-multimodal-demo.\n",
        encoding="utf-8",
    )
    keyframe_ocr_path.write_text(
        "Week07 Video Evidence\n"
        "Step 1: validate identity\n"
        "Step 2: replay recovery steps\n"
        "Step 3: cite evidence anchors\n",
        encoding="utf-8",
    )

    assets = [
        {
            "source_id": "doc:week07:pdf001",
            "source_url_or_path": "data/week07_media/workspace_recovery_manual.pdf",
            "asset_type": "pdf",
            "contract_ref": "omni://contracts/data/doc_asset/v1",
            "size_bytes": pdf_path.stat().st_size,
            "checksum_sha256": _sha256(pdf_path),
            "metadata_status": "complete",
            "pii_scan_status": "clear",
            "language": "en",
            "notes": "Real PDF fixture with extractable recovery policy text.",
        },
        {
            "source_id": "image:week07:ocr001",
            "source_url_or_path": "data/week07_media/workspace_recovery_evidence.png",
            "asset_type": "image",
            "contract_ref": "omni://contracts/data/doc_asset/v1",
            "ocr_text_path": "data/week07_media/workspace_recovery_evidence.ocr.txt",
            "size_bytes": image_path.stat().st_size,
            "checksum_sha256": _sha256(image_path),
            "metadata_status": "complete",
            "pii_scan_status": "clear",
            "language": "en",
            "notes": "Real PNG fixture for OCR and image evidence anchoring.",
        },
        {
            "source_id": "audio:week07:call001",
            "source_url_or_path": "data/week07_media/support_call_recovery.wav",
            "asset_type": "audio",
            "contract_ref": "omni://contracts/data/audio_asset/v1",
            "transcript_object_path": "data/week07_media/support_call_recovery.transcript.jsonl",
            "size_bytes": audio_path.stat().st_size,
            "checksum_sha256": _sha256(audio_path),
            "metadata_status": "complete",
            "pii_scan_status": "clear",
            "duration_sec": 5.0,
            "language": "en",
            "notes": "Real WAV fixture plus ASR-style transcript sidecar.",
        },
        {
            "source_id": "video:week07:demo001",
            "source_url_or_path": "data/week07_media/workspace_recovery_demo.mp4",
            "asset_type": "video",
            "contract_ref": "omni://contracts/data/video_asset/v1",
            "transcript_object_path": "data/week07_media/workspace_recovery_demo.transcript.jsonl",
            "keyframe_ocr_path": "data/week07_media/workspace_recovery_demo.keyframe_ocr.txt",
            "audio_track_path": "data/week07_media/support_call_recovery.wav",
            "size_bytes": video_path.stat().st_size if video_path.exists() else None,
            "checksum_sha256": _sha256(video_path) if video_path.exists() else None,
            "metadata_status": "complete",
            "pii_scan_status": "clear",
            "duration_sec": 5.0,
            "language": "en",
            "notes": "Real MP4 fixture with transcript and keyframe OCR evidence.",
        },
    ]
    manifest = {
        "manifest_id": "manifest-week07-multimodal-20260424-001",
        "schema_version": "source_manifest_v1",
        "batch_id": "batch-20260424-007",
        "modality": "multimodal",
        "source_type": "other",
        "product_line": "northstar_workspace",
        "license_tag": "course_synthetic",
        "contract_ref": "omni://contracts/data/doc_asset/v1",
        "load_mode": "full_snapshot",
        "canonization_status": "canonized",
        "gate_policy": {
            "on_missing_checksum": "reject",
            "on_partial_metadata": "warn",
            "on_missing_metadata": "quarantine",
            "on_pii_gap": "quarantine",
            "on_contract_mismatch": "reject",
            "on_unknown_license": "reject",
        },
        "assets": assets,
        "ingest_config": {
            "parser": "auto",
            "chunk_size": 320,
            "chunk_overlap": 40,
            "pii_scan": True,
        },
        "created_at": "2026-04-24T00:00:00Z",
        "owner": "course-team",
        "notes": "Week07 real multimodal fixtures for PDF, image OCR, audio transcript, and video keyframe/transcript parsing.",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {MANIFEST_PATH}")


if __name__ == "__main__":
    main()

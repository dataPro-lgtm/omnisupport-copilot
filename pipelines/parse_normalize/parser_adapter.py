"""Parser adapter routing for Week07 document and media normalization."""

from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import tempfile
import wave
import shutil

from pipelines.parse_normalize.models import (
    DEFAULT_PARSE_STRATEGY_VERSION,
    ParsedSection,
    ParserCapability,
    SourceDocument,
    stable_id,
)


SECTION_SPLIT_RE = re.compile(r"\n\s*\n+")
TEXT_ASSET_TYPES = {"html", "faq", "release_notes", "api_doc", "community_post", "other"}


def _base_warning(document: SourceDocument, parser_name: str) -> list[str]:
    warnings = list(document.warnings)
    if parser_name == "fallback":
        warnings.append("fallback_parser_used")
    return sorted(set(warnings))


def _capability(
    *,
    parser_name: str,
    asset_type: str,
    fallback_used: bool,
    warnings: list[str],
) -> ParserCapability:
    if parser_name == "docling" and not fallback_used:
        return ParserCapability(
            preserves_page=True,
            preserves_bbox=True,
            preserves_table=True,
            fallback_used=False,
            warnings=warnings,
        )
    if parser_name == "pypdf" and not fallback_used:
        return ParserCapability(
            preserves_page=True,
            preserves_bbox=False,
            preserves_table=False,
            fallback_used=False,
            extracts_media_metadata=False,
            warnings=warnings,
        )
    if parser_name == "unstructured" and not fallback_used:
        return ParserCapability(
            preserves_page=asset_type == "pdf",
            preserves_bbox=False,
            preserves_table=True,
            fallback_used=False,
            warnings=warnings,
        )
    if parser_name in {"tesseract_ocr", "ocr_sidecar"} and not fallback_used:
        return ParserCapability(
            preserves_page=False,
            preserves_bbox=False,
            preserves_table=False,
            fallback_used=False,
            extracts_ocr=True,
            extracts_media_metadata=True,
            warnings=warnings,
        )
    if parser_name in {"audio_transcript_sidecar", "video_ffmpeg_sidecar"} and not fallback_used:
        return ParserCapability(
            preserves_page=False,
            preserves_bbox=False,
            preserves_table=False,
            fallback_used=False,
            extracts_ocr=parser_name == "video_ffmpeg_sidecar",
            extracts_transcript=True,
            extracts_media_metadata=True,
            extracts_keyframes=parser_name == "video_ffmpeg_sidecar",
            warnings=warnings,
        )
    return ParserCapability(
        preserves_page=asset_type == "pdf",
        preserves_bbox=False,
        preserves_table=False,
        fallback_used=True,
        warnings=warnings,
    )


def _paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    parts = [p.strip() for p in SECTION_SPLIT_RE.split(normalized) if p.strip()]
    if parts:
        return parts
    return [normalized]


def _section_type_for(text: str, index: int) -> str:
    if index == 0 and len(text) <= 120:
        return "title"
    if text.lstrip().startswith(("-", "*", "1.")):
        return "list"
    return "text"


def _section(
    document: SourceDocument,
    *,
    index: int,
    section_path: str,
    section_type: str,
    content: str,
    parser_backend: str,
    capability: dict,
    parse_strategy_version: str,
    page_no: int | None = None,
    bbox: list[float] | None = None,
    bbox_missing_reason: str | None = None,
    metadata: dict | None = None,
) -> ParsedSection:
    section_id = stable_id(
        "section",
        document.source_fingerprint,
        document.doc_id,
        index,
        section_path,
        content[:120],
    )
    return ParsedSection(
        section_id=section_id,
        doc_id=document.doc_id,
        source_id=document.source_id,
        source_fingerprint=document.source_fingerprint,
        asset_type=document.asset_type,
        section_index=index,
        section_path=section_path or f"section_{index}",
        section_type=section_type,
        content=content,
        page_no=page_no,
        bbox=bbox,
        bbox_missing_reason=bbox_missing_reason,
        parser_backend=parser_backend,
        parser_capability=capability,
        parse_strategy_version=parse_strategy_version,
        data_release_id=document.data_release_id,
        doc_version=document.doc_version,
        source_url_or_path=document.source_url_or_path,
        metadata={
            "manifest_id": document.manifest_id,
            "batch_id": document.batch_id,
            "raw_available": document.raw_available,
            **(metadata or {}),
        },
    )


def _fallback_parse(
    document: SourceDocument,
    *,
    parser_backend: str,
    parse_strategy_version: str,
    warnings: list[str],
) -> list[ParsedSection]:
    capability = _capability(
        parser_name=parser_backend,
        asset_type=document.asset_type,
        fallback_used=True,
        warnings=warnings,
    ).to_dict()
    sections: list[ParsedSection] = []
    for index, paragraph in enumerate(_paragraphs(document.raw_text)):
        page_no = 1 if document.asset_type == "pdf" else None
        bbox_missing_reason = "fallback_parser_no_bbox" if document.asset_type == "pdf" else None
        section_path = paragraph.splitlines()[0][:80] if paragraph else f"section_{index}"
        sections.append(
            _section(
                document,
                index=index,
                section_path=section_path,
                section_type=_section_type_for(paragraph, index),
                content=paragraph,
                parser_backend="fallback",
                capability=capability,
                parse_strategy_version=parse_strategy_version,
                page_no=page_no,
                bbox_missing_reason=bbox_missing_reason,
            )
        )
    return sections


def _parse_with_pypdf(
    document: SourceDocument,
    *,
    parse_strategy_version: str,
    warnings: list[str],
) -> list[ParsedSection]:
    try:
        from pypdf import PdfReader
    except Exception:
        warnings.append("pypdf_unavailable_fallback_used")
        return _fallback_parse(
            document,
            parser_backend="fallback",
            parse_strategy_version=parse_strategy_version,
            warnings=warnings,
        )

    reader = PdfReader(BytesIO(document.raw_bytes))
    capability = _capability(
        parser_name="pypdf",
        asset_type=document.asset_type,
        fallback_used=False,
        warnings=warnings,
    ).to_dict()
    sections: list[ParsedSection] = []
    section_index = 0
    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for paragraph_index, paragraph in enumerate(_paragraphs(text)):
            section_path = f"page/{page_index}/paragraph/{paragraph_index}"
            sections.append(
                _section(
                    document,
                    index=section_index,
                    section_path=section_path,
                    section_type=_section_type_for(paragraph, section_index),
                    content=paragraph,
                    parser_backend="pypdf",
                    capability=capability,
                    parse_strategy_version=parse_strategy_version,
                    page_no=page_index,
                    bbox=None,
                    bbox_missing_reason="pypdf_no_bbox",
                    metadata={"page_index": page_index, "paragraph_index": paragraph_index},
                )
            )
            section_index += 1
    if not sections:
        warnings.append("pdf_text_empty")
    return sections


def _parse_with_unstructured(
    document: SourceDocument,
    *,
    parse_strategy_version: str,
    warnings: list[str],
) -> list[ParsedSection]:
    try:
        from unstructured.partition.text import partition_text
    except Exception:
        warnings.append("unstructured_unavailable_fallback_used")
        return _fallback_parse(
            document,
            parser_backend="fallback",
            parse_strategy_version=parse_strategy_version,
            warnings=warnings,
        )

    elements = partition_text(text=document.raw_text)
    capability = _capability(
        parser_name="unstructured",
        asset_type=document.asset_type,
        fallback_used=False,
        warnings=warnings,
    ).to_dict()
    sections: list[ParsedSection] = []
    for index, element in enumerate(elements):
        content = str(element).strip()
        if not content:
            continue
        section_path = content.splitlines()[0][:80]
        section_id = stable_id("section", document.source_fingerprint, document.doc_id, index, section_path)
        sections.append(
            ParsedSection(
                section_id=section_id,
                doc_id=document.doc_id,
                source_id=document.source_id,
                source_fingerprint=document.source_fingerprint,
                asset_type=document.asset_type,
                section_index=index,
                section_path=section_path or f"section_{index}",
                section_type=_section_type_for(content, index),
                content=content,
                page_no=None,
                bbox=None,
                bbox_missing_reason=None,
                parser_backend="unstructured",
                parser_capability=capability,
                parse_strategy_version=parse_strategy_version,
                data_release_id=document.data_release_id,
                doc_version=document.doc_version,
                source_url_or_path=document.source_url_or_path,
                metadata={"manifest_id": document.manifest_id, "batch_id": document.batch_id},
            )
        )
    return sections


def _run_json(command: list[str]) -> dict:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout or "{}")


def _ffmpeg_exe() -> str | None:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _audio_metadata(document: SourceDocument) -> dict:
    path = document.raw_path
    if path and path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as audio:
            frame_count = audio.getnframes()
            frame_rate = audio.getframerate()
            return {
                "duration_sec": round(frame_count / frame_rate, 3) if frame_rate else None,
                "sample_rate_hz": frame_rate,
                "channels": audio.getnchannels(),
                "sample_width": audio.getsampwidth(),
                "container": "wav",
            }
    if path:
        try:
            payload = _run_json(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration:stream=codec_type,codec_name,sample_rate,channels",
                    "-of",
                    "json",
                    str(path),
                ]
            )
            return {"container": path.suffix.lower().lstrip("."), "ffprobe": payload}
        except Exception as exc:
            return {"metadata_error": str(exc)}
    return {}


def _video_metadata(document: SourceDocument) -> dict:
    path = document.raw_path
    if not path:
        return {}
    try:
        import imageio_ffmpeg

        reader = imageio_ffmpeg.read_frames(str(path), pix_fmt="rgb24")
        metadata = next(reader)
        reader.close()
        return {
            "duration_sec": metadata.get("duration"),
            "width": metadata.get("size", [None, None])[0],
            "height": metadata.get("size", [None, None])[1],
            "fps": metadata.get("fps"),
            "source": "imageio_ffmpeg",
        }
    except Exception:
        pass
    try:
        payload = _run_json(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=index,codec_type,codec_name,width,height",
                "-of",
                "json",
                str(path),
            ]
        )
        video_stream = next(
            (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
            {},
        )
        return {
            "duration_sec": float(payload.get("format", {}).get("duration") or 0),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "video_codec": video_stream.get("codec_name"),
            "ffprobe": payload,
        }
    except Exception as exc:
        return {"metadata_error": str(exc)}


def _parse_transcript(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
            rows.append(
                {
                    "text": str(payload.get("text") or payload.get("content") or "").strip(),
                    "speaker": payload.get("speaker") or payload.get("speaker_role"),
                    "start_ts": payload.get("start_ts", payload.get("start")),
                    "end_ts": payload.get("end_ts", payload.get("end")),
                }
            )
        except json.JSONDecodeError:
            rows.append({"text": stripped, "speaker": None, "start_ts": None, "end_ts": None})
    if not rows and text.strip():
        rows.append({"text": text.strip(), "speaker": None, "start_ts": None, "end_ts": None})
    return [row for row in rows if row["text"]]


def _ocr_bytes(raw_bytes: bytes, warnings: list[str], warning_prefix: str) -> str:
    try:
        from PIL import Image
        import pytesseract
    except Exception as exc:
        warnings.append(f"{warning_prefix}_ocr_dependency_unavailable")
        warnings.append(type(exc).__name__)
        return ""
    try:
        image = Image.open(BytesIO(raw_bytes))
        return pytesseract.image_to_string(image).strip()
    except Exception:
        warnings.append(f"{warning_prefix}_ocr_failed")
        return ""


def _parse_image(
    document: SourceDocument,
    *,
    parse_strategy_version: str,
    warnings: list[str],
) -> list[ParsedSection]:
    ocr_text = _ocr_bytes(document.raw_bytes, warnings, "image")
    parser_backend = "tesseract_ocr"
    if not ocr_text and document.sidecars.get("ocr_text"):
        ocr_text = document.sidecars["ocr_text"].strip()
        parser_backend = "ocr_sidecar"
    if not ocr_text:
        warnings.append("image_ocr_text_empty")
        return []

    capability = _capability(
        parser_name=parser_backend,
        asset_type=document.asset_type,
        fallback_used=False,
        warnings=warnings,
    ).to_dict()
    return [
        _section(
            document,
            index=0,
            section_path="image/ocr",
            section_type="image",
            content=ocr_text,
            parser_backend=parser_backend,
            capability=capability,
            parse_strategy_version=parse_strategy_version,
            metadata={"ocr_source": parser_backend},
        )
    ]


def _parse_audio(
    document: SourceDocument,
    *,
    parse_strategy_version: str,
    warnings: list[str],
) -> list[ParsedSection]:
    transcript = document.sidecars.get("transcript", "")
    rows = _parse_transcript(transcript)
    if not rows:
        warnings.append("audio_transcript_sidecar_missing")
        return []

    capability = _capability(
        parser_name="audio_transcript_sidecar",
        asset_type=document.asset_type,
        fallback_used=False,
        warnings=warnings,
    ).to_dict()
    media_metadata = _audio_metadata(document)
    sections: list[ParsedSection] = []
    for index, row in enumerate(rows):
        speaker = row.get("speaker") or "speaker"
        start_ts = row.get("start_ts")
        end_ts = row.get("end_ts")
        section_path = f"audio/{speaker}/{start_ts or index}"
        sections.append(
            _section(
                document,
                index=index,
                section_path=section_path,
                section_type="transcript",
                content=row["text"],
                parser_backend="audio_transcript_sidecar",
                capability=capability,
                parse_strategy_version=parse_strategy_version,
                metadata={
                    "speaker": speaker,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "media": media_metadata,
                },
            )
        )
    return sections


def _extract_first_keyframe_ocr(document: SourceDocument, warnings: list[str]) -> str:
    if not document.raw_path:
        return ""
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        warnings.append("video_ffmpeg_unavailable")
        return ""
    with tempfile.NamedTemporaryFile(suffix=".png") as image_file:
        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(document.raw_path),
                    "-frames:v",
                    "1",
                    image_file.name,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return _ocr_bytes(Path(image_file.name).read_bytes(), warnings, "video_keyframe")
        except Exception:
            warnings.append("video_keyframe_extract_failed")
            return ""


def _parse_video(
    document: SourceDocument,
    *,
    parse_strategy_version: str,
    warnings: list[str],
) -> list[ParsedSection]:
    transcript_rows = _parse_transcript(document.sidecars.get("transcript", ""))
    keyframe_text = _extract_first_keyframe_ocr(document, warnings)
    if not keyframe_text and document.sidecars.get("keyframe_ocr"):
        keyframe_text = document.sidecars["keyframe_ocr"].strip()

    if not transcript_rows and not keyframe_text:
        warnings.append("video_no_transcript_or_keyframe_ocr")
        return []

    capability = _capability(
        parser_name="video_ffmpeg_sidecar",
        asset_type=document.asset_type,
        fallback_used=False,
        warnings=warnings,
    ).to_dict()
    media_metadata = _video_metadata(document)
    sections: list[ParsedSection] = []
    index = 0
    for row in transcript_rows:
        start_ts = row.get("start_ts")
        end_ts = row.get("end_ts")
        sections.append(
            _section(
                document,
                index=index,
                section_path=f"video/transcript/{start_ts or index}",
                section_type="transcript",
                content=row["text"],
                parser_backend="video_ffmpeg_sidecar",
                capability=capability,
                parse_strategy_version=parse_strategy_version,
                metadata={
                    "speaker": row.get("speaker") or "narrator",
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "media": media_metadata,
                },
            )
        )
        index += 1

    if keyframe_text:
        sections.append(
            _section(
                document,
                index=index,
                section_path="video/keyframe/0",
                section_type="image",
                content=keyframe_text,
                parser_backend="video_ffmpeg_sidecar",
                capability=capability,
                parse_strategy_version=parse_strategy_version,
                metadata={"frame_ts": 0.0, "media": media_metadata},
            )
        )
    return sections


def parse_document(
    document: SourceDocument,
    *,
    parser: str = "auto",
    parse_strategy_version: str = DEFAULT_PARSE_STRATEGY_VERSION,
) -> list[ParsedSection]:
    requested = parser
    if parser == "auto":
        if document.asset_type == "pdf":
            requested = "pypdf"
        elif document.asset_type == "image":
            requested = "ocr"
        elif document.asset_type in {"audio", "video"}:
            requested = "media"
        else:
            requested = "unstructured"

    warnings = _base_warning(document, "fallback" if requested == "fallback" else requested)

    if requested == "fallback":
        return _fallback_parse(
            document,
            parser_backend="fallback",
            parse_strategy_version=parse_strategy_version,
            warnings=warnings,
        )

    if requested == "unstructured":
        return _parse_with_unstructured(
            document,
            parse_strategy_version=parse_strategy_version,
            warnings=warnings,
        )

    if requested == "pypdf":
        return _parse_with_pypdf(
            document,
            parse_strategy_version=parse_strategy_version,
            warnings=warnings,
        )

    if requested == "ocr":
        return _parse_image(
            document,
            parse_strategy_version=parse_strategy_version,
            warnings=warnings,
        )

    if requested == "media":
        if document.asset_type == "audio":
            return _parse_audio(
                document,
                parse_strategy_version=parse_strategy_version,
                warnings=warnings,
            )
        if document.asset_type == "video":
            return _parse_video(
                document,
                parse_strategy_version=parse_strategy_version,
                warnings=warnings,
            )
        raise ValueError(f"Media parser supports audio/video, got {document.asset_type}")

    if requested == "docling":
        try:
            from docling.document_converter import DocumentConverter  # noqa: F401
        except Exception:
            warnings.append("docling_unavailable_fallback_used")
            return _fallback_parse(
                document,
                parser_backend="fallback",
                parse_strategy_version=parse_strategy_version,
                warnings=warnings,
            )
        warnings.append("docling_adapter_minimal_fallback_used")
        return _fallback_parse(
            document,
            parser_backend="fallback",
            parse_strategy_version=parse_strategy_version,
            warnings=warnings,
        )

    raise ValueError(f"Unsupported parser: {parser}")


def parse_documents(
    documents: list[SourceDocument],
    *,
    parser: str = "auto",
    parse_strategy_version: str = DEFAULT_PARSE_STRATEGY_VERSION,
) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    for document in documents:
        sections.extend(
            parse_document(
                document,
                parser=parser,
                parse_strategy_version=parse_strategy_version,
            )
        )
    return sections

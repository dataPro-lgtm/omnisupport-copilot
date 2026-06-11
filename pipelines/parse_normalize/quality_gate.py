"""Week07 chunk quality gate."""

from dataclasses import dataclass, field
import re

from pipelines.parse_normalize.models import DocumentChunk, EvidenceAnchor, ParsedSection, stable_id
from pipelines.quality.report import build_quality_report


PII_RE = re.compile(
    r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})|(\b\d{3}[-.]?\d{2}[-.]?\d{4}\b)",
    re.IGNORECASE,
)
MEDIA_BLOCKING_REASON_CODES = {
    "audio_transcript_sidecar_missing",
    "image_ocr_text_empty",
    "video_no_transcript_or_keyframe_ocr",
    "media_binary_text_fallback_blocked",
}


@dataclass
class QualityGateResult:
    quality_status: str
    week8_ready: bool
    metrics: dict
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    samples: list[dict] = field(default_factory=list)


def _metadata_complete(chunk: DocumentChunk) -> bool:
    required_values = [
        chunk.chunk_id,
        chunk.doc_id,
        chunk.source_id,
        chunk.section_id,
        chunk.source_fingerprint,
        chunk.chunk_strategy_version,
        chunk.parse_strategy_version,
        chunk.data_release_id,
    ]
    return all(bool(value) for value in required_values)


def evaluate_quality_gate(
    sections: list[ParsedSection],
    chunks: list[DocumentChunk],
    anchors: list[EvidenceAnchor],
) -> QualityGateResult:
    anchor_chunk_ids = {anchor.chunk_id for anchor in anchors}
    section_ids = {section.section_id for section in sections}
    chunk_ids = {chunk.chunk_id for chunk in chunks}

    empty_chunks = [chunk.chunk_id for chunk in chunks if not chunk.content.strip()]
    unanchored_chunks = [chunk.chunk_id for chunk in chunks if chunk.chunk_id not in anchor_chunk_ids]
    orphan_chunks = [chunk.chunk_id for chunk in chunks if chunk.section_id not in section_ids]
    orphan_anchors = [anchor.anchor_id for anchor in anchors if anchor.chunk_id not in chunk_ids]
    pdf_missing_page = [
        anchor.anchor_id for anchor in anchors if anchor.asset_type == "pdf" and anchor.page_no is None
    ]
    pdf_missing_bbox_reason = [
        anchor.anchor_id
        for anchor in anchors
        if anchor.asset_type == "pdf" and anchor.bbox is None and not anchor.bbox_missing_reason
    ]
    fallback_chunks = [chunk.chunk_id for chunk in chunks if "fallback_parser_used" in chunk.reason_codes]
    synthetic_chunks = [
        chunk.chunk_id for chunk in chunks if "source_path_missing_synthetic_fallback" in chunk.reason_codes
    ]
    media_blocked_chunks = [
        chunk.chunk_id
        for chunk in chunks
        if MEDIA_BLOCKING_REASON_CODES.intersection(set(chunk.reason_codes))
    ]
    pii_chunks = [chunk for chunk in chunks if PII_RE.search(chunk.content)]
    metadata_complete = sum(1 for chunk in chunks if _metadata_complete(chunk))
    metadata_completeness = metadata_complete / len(chunks) if chunks else 0.0
    anchor_coverage = (len(chunks) - len(unanchored_chunks)) / len(chunks) if chunks else 0.0

    errors: list[str] = []
    warnings: list[str] = []
    if not chunks:
        errors.append("no_chunks")
    if empty_chunks:
        errors.append("empty_chunks")
    if unanchored_chunks:
        errors.append("missing_evidence_anchor")
    if orphan_chunks:
        errors.append("orphan_chunks")
    if orphan_anchors:
        errors.append("orphan_anchors")
    if pdf_missing_page:
        errors.append("pdf_missing_page_no")
    if pdf_missing_bbox_reason:
        errors.append("pdf_missing_bbox_reason")
    if metadata_completeness < 1.0:
        warnings.append("metadata_incomplete")
    if fallback_chunks:
        warnings.append("fallback_parser_used")
    if synthetic_chunks:
        warnings.append("source_path_missing_synthetic_fallback")
    if media_blocked_chunks:
        errors.append("media_extraction_incomplete")
    if pii_chunks:
        warnings.append("pii_suspected")

    quality_status = "fail" if errors else "warn" if warnings else "pass"
    week8_ready = bool(chunks) and not errors and not synthetic_chunks

    for chunk in chunks:
        chunk.pii_detected = bool(PII_RE.search(chunk.content))
        chunk.allowed_for_indexing = (
            chunk.anchor_count > 0
            and bool(chunk.content.strip())
            and "source_path_missing_synthetic_fallback" not in chunk.reason_codes
            and not MEDIA_BLOCKING_REASON_CODES.intersection(set(chunk.reason_codes))
            and not chunk.pii_detected
        )
        chunk.quality_status = "fail" if not chunk.allowed_for_indexing and not synthetic_chunks else quality_status
        if chunk.pii_detected and "pii_suspected" not in chunk.reason_codes:
            chunk.reason_codes.append("pii_suspected")

    samples = []
    for chunk in chunks[: min(5, len(chunks))]:
        reason_codes = list(chunk.reason_codes)
        status = "fail" if not chunk.content.strip() or chunk.anchor_count == 0 else "warn" if reason_codes else "pass"
        samples.append(
            {
                "sample_id": stable_id("quality-sample", chunk.chunk_id, chunk.source_fingerprint),
                "chunk_id": chunk.chunk_id,
                "section_id": chunk.section_id,
                "status": status,
                "reason_codes": reason_codes,
                "checks": {
                    "has_content": bool(chunk.content.strip()),
                    "has_anchor": chunk.anchor_count > 0,
                    "has_source_fingerprint": bool(chunk.source_fingerprint),
                    "pii_suspected": chunk.pii_detected,
                    "notes": "Sampled by Week07 quality gate.",
                },
            }
        )

    metrics = {
        "section_count": len(sections),
        "chunk_count": len(chunks),
        "anchor_count": len(anchors),
        "metadata_completeness": round(metadata_completeness, 4),
        "anchor_coverage": round(anchor_coverage, 4),
        "empty_chunk_count": len(empty_chunks),
        "unanchored_chunk_count": len(unanchored_chunks),
        "orphan_chunk_count": len(orphan_chunks),
        "orphan_anchor_count": len(orphan_anchors),
        "pdf_missing_page_count": len(pdf_missing_page),
        "fallback_chunk_count": len(fallback_chunks),
        "synthetic_source_chunk_count": len(synthetic_chunks),
        "media_blocked_chunk_count": len(media_blocked_chunks),
        "pii_suspected_chunk_count": len(pii_chunks),
        "allowed_for_indexing_count": sum(1 for chunk in chunks if chunk.allowed_for_indexing),
    }

    result = QualityGateResult(
        quality_status=quality_status,
        week8_ready=week8_ready,
        metrics=metrics,
        warnings=sorted(set(warnings)),
        errors=sorted(set(errors)),
        samples=samples,
    )
    quality_report = build_quality_report(result)
    result.metrics.update(
        {
            "gate_decision": quality_report.gate_decision,
            "completeness_score": quality_report.completeness_score,
            "noise_score": quality_report.noise_score,
            "evidence_score": quality_report.evidence_score,
            "coherence_score": quality_report.coherence_score,
        }
    )
    return result

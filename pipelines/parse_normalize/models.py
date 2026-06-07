"""Week07 parse/normalize data models."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_PARSE_STRATEGY_VERSION = "parse_normalize_v1"
DEFAULT_CHUNK_STRATEGY_VERSION = "section_aware_v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, *parts: object, length: int = 24) -> str:
    raw = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


@dataclass
class ParserCapability:
    preserves_page: bool
    preserves_bbox: bool
    preserves_table: bool
    fallback_used: bool
    extracts_ocr: bool = False
    extracts_transcript: bool = False
    extracts_media_metadata: bool = False
    extracts_keyframes: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SourceDocument:
    source_id: str
    doc_id: str
    asset_type: str
    source_url_or_path: str
    raw_text: str
    raw_bytes: bytes
    source_fingerprint: str
    manifest_id: str | None
    batch_id: str | None
    doc_version: str
    data_release_id: str
    product_line: str | None = None
    license_tag: str | None = None
    raw_available: bool = True
    raw_path: Path | None = None
    sidecars: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParsedSection:
    section_id: str
    doc_id: str
    source_id: str
    source_fingerprint: str
    asset_type: str
    section_index: int
    section_path: str
    section_type: str
    content: str
    page_no: int | None
    bbox: list[float] | None
    bbox_missing_reason: str | None
    parser_backend: str
    parser_capability: dict
    parse_strategy_version: str
    data_release_id: str
    doc_version: str
    source_url_or_path: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    source_id: str
    section_id: str
    source_fingerprint: str
    chunk_index: int
    section_chunk_index: int
    chunk_strategy_version: str
    parse_strategy_version: str
    data_release_id: str
    doc_version: str | None
    section_path: str | None
    section_type: str | None
    content: str
    page_no: int | None
    bbox: list[float] | None
    asset_type: str = "other"
    parser_backend: str = "fallback"
    parser_capability: dict = field(default_factory=dict)
    evidence_anchor_ids: list[str] = field(default_factory=list)
    anchor_count: int = 0
    quality_status: str = "warn"
    allowed_for_indexing: bool = False
    pii_detected: bool = False
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvidenceAnchor:
    anchor_id: str
    chunk_id: str
    section_id: str
    doc_id: str
    source_id: str
    source_fingerprint: str
    asset_type: str
    anchor_type: str
    source_url_or_path: str
    section_path: str
    doc_version: str
    page_no: int | None
    bbox: list[float] | None
    bbox_missing_reason: str | None
    parser_backend: str
    parser_capability: dict
    data_release_id: str
    created_at: str
    start_ts: float | None = None
    end_ts: float | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParseArtifacts:
    sections: str
    chunks: str
    evidence_anchors: str
    quality_samples: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParseRunReport:
    parse_run_id: str
    status: str
    manifest_id: str | None
    batch_id: str | None
    parser: str
    chunk_strategy_version: str
    parse_strategy_version: str
    data_release_id: str
    started_at: str
    finished_at: str
    source_count: int
    section_count: int
    chunk_count: int
    anchor_count: int
    quality_status: str
    week8_ready: bool
    warnings: list[str]
    errors: list[str]
    artifacts: dict

    def to_dict(self) -> dict:
        return asdict(self)

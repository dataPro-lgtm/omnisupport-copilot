"""Load Week07 document sources from manifests or local files."""

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from pipelines.parse_normalize.models import SourceDocument, sha256_bytes, stable_id


BINARY_ASSET_TYPES = {"pdf", "image", "audio", "video"}
TEXT_SIDECAR_FIELDS = {
    "transcript": ("transcript_object_path", "audio_track_transcript_path"),
    "ocr_text": ("ocr_text_path", "image_ocr_path"),
    "keyframe_ocr": ("keyframe_ocr_path",),
}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return "\n\n".join(self._parts)


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text())


def _path_from_uri(value: str) -> Path | None:
    parsed = urlparse(value)
    if parsed.scheme == "file":
        return Path(parsed.path)
    if parsed.scheme:
        return None
    return Path(value)


def _decode_text(raw: bytes, asset_type: str, *, raw_available: bool) -> str:
    if raw_available and asset_type in BINARY_ASSET_TYPES:
        return ""
    text = raw.decode("utf-8", errors="ignore")
    if asset_type in {"html", "faq", "release_notes", "api_doc", "community_post"}:
        parser = _HTMLTextExtractor()
        parser.feed(text)
        stripped = parser.text()
        return stripped or text
    return text


def _read_sidecar_text(path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = _path_from_uri(path_value)
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _discover_adjacent_sidecar(candidate_path: Path | None, suffixes: tuple[str, ...]) -> str | None:
    if not candidate_path:
        return None
    for suffix in suffixes:
        path = candidate_path.with_suffix(candidate_path.suffix + suffix)
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


def _load_sidecars(asset: dict, candidate_path: Path | None) -> dict[str, str]:
    sidecars: dict[str, str] = {}
    for sidecar_name, fields in TEXT_SIDECAR_FIELDS.items():
        for field in fields:
            text = _read_sidecar_text(asset.get(field))
            if text is not None:
                sidecars[sidecar_name] = text
                break

    sidecars.setdefault(
        "transcript",
        _discover_adjacent_sidecar(candidate_path, (".transcript.jsonl", ".transcript.txt", ".vtt")) or "",
    )
    sidecars.setdefault(
        "ocr_text",
        _discover_adjacent_sidecar(candidate_path, (".ocr.txt", ".ocr.md")) or "",
    )
    sidecars.setdefault(
        "keyframe_ocr",
        _discover_adjacent_sidecar(candidate_path, (".keyframe_ocr.txt", ".keyframes.txt")) or "",
    )
    return {key: value for key, value in sidecars.items() if value.strip()}


def _synthetic_source_text(asset: dict, manifest: dict) -> str:
    notes = asset.get("notes") or "Course placeholder document"
    source_id = asset.get("source_id", "unknown-source")
    source_path = asset.get("source_url_or_path", "unknown-source-path")
    product = manifest.get("product_line", "unknown")
    return (
        f"{notes}\n\n"
        f"Source ID: {source_id}\n\n"
        f"Product line: {product}\n\n"
        f"Original path: {source_path}\n\n"
        "Week07 fallback content is generated from manifest metadata because the raw "
        "object is not available in the local classroom checkout. Replace this with "
        "a real file or object-store fetch for production parsing."
    )


def _document_from_asset(
    *,
    asset: dict,
    manifest: dict,
    data_release_id: str,
    expected_fingerprint: str | None = None,
    input_path: Path | None = None,
    content_type: str | None = None,
) -> SourceDocument:
    source_id = asset["source_id"]
    asset_type = content_type or asset.get("asset_type") or "other"
    source_url_or_path = str(input_path or asset.get("source_url_or_path") or "")
    doc_version = asset.get("doc_version") or manifest.get("manifest_id") or "unversioned"
    warnings: list[str] = []
    raw_available = False

    candidate_path = input_path or _path_from_uri(source_url_or_path)
    if candidate_path and candidate_path.exists():
        raw_bytes = candidate_path.read_bytes()
        raw_available = True
    else:
        raw_text = _synthetic_source_text(asset, manifest)
        raw_bytes = raw_text.encode("utf-8")
        warnings.append("source_path_missing_synthetic_fallback")

    source_fingerprint = sha256_bytes(raw_bytes)
    declared_checksum = asset.get("checksum_sha256")
    if expected_fingerprint and source_fingerprint != expected_fingerprint:
        raise ValueError(
            f"source_fingerprint mismatch for {source_id}: "
            f"expected {expected_fingerprint}, got {source_fingerprint}"
        )
    if raw_available and declared_checksum and source_fingerprint != declared_checksum:
        raise ValueError(
            f"manifest checksum mismatch for {source_id}: "
            f"declared {declared_checksum}, got {source_fingerprint}"
        )
    if not raw_available and declared_checksum and source_fingerprint != declared_checksum:
        warnings.append("manifest_checksum_not_recomputed_from_raw")

    raw_text = _decode_text(raw_bytes, asset_type, raw_available=raw_available)
    doc_id = stable_id("doc", source_id, doc_version)
    return SourceDocument(
        source_id=source_id,
        doc_id=doc_id,
        asset_type=asset_type,
        source_url_or_path=source_url_or_path,
        raw_text=raw_text,
        raw_bytes=raw_bytes,
        source_fingerprint=source_fingerprint,
        manifest_id=manifest.get("manifest_id"),
        batch_id=manifest.get("batch_id"),
        doc_version=doc_version,
        data_release_id=data_release_id,
        product_line=manifest.get("product_line"),
        license_tag=manifest.get("license_tag"),
        raw_available=raw_available,
        raw_path=candidate_path if candidate_path and candidate_path.exists() else None,
        sidecars=_load_sidecars(asset, candidate_path if candidate_path and candidate_path.exists() else None),
        warnings=warnings,
    )


def load_sources(
    *,
    manifest_path: Path | None,
    source_id: str | None,
    input_path: Path | None,
    content_type: str | None,
    data_release_id: str,
    expected_fingerprint: str | None = None,
) -> tuple[dict, list[SourceDocument]]:
    if manifest_path:
        manifest = load_manifest(manifest_path)
    else:
        if not input_path:
            raise ValueError("Either --manifest-path or --input-path is required.")
        manifest = {
            "manifest_id": f"manifest-local-{stable_id('src', input_path, length=12)}",
            "batch_id": "batch-local-week07",
            "product_line": "unknown",
            "license_tag": "unknown",
            "assets": [
                {
                    "source_id": source_id or stable_id("doc:local", input_path, length=12),
                    "source_url_or_path": str(input_path),
                    "asset_type": content_type or "other",
                }
            ],
        }

    assets = manifest.get("assets", [])
    if source_id:
        assets = [a for a in assets if a.get("source_id") == source_id]
    if not assets:
        raise ValueError(f"No matching document assets found in manifest: {manifest_path}")

    documents = [
        _document_from_asset(
            asset=asset,
            manifest=manifest,
            data_release_id=data_release_id,
            expected_fingerprint=expected_fingerprint,
            input_path=input_path if len(assets) == 1 else None,
            content_type=content_type,
        )
        for asset in assets
    ]
    return manifest, documents

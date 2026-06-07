"""Section-aware chunking for Week07."""

from pipelines.parse_normalize.models import (
    DEFAULT_CHUNK_STRATEGY_VERSION,
    DocumentChunk,
    ParsedSection,
    stable_id,
)


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_sections(
    sections: list[ParsedSection],
    *,
    chunk_strategy_version: str = DEFAULT_CHUNK_STRATEGY_VERSION,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[DocumentChunk]:
    if chunk_strategy_version != DEFAULT_CHUNK_STRATEGY_VERSION:
        raise ValueError(f"Unsupported chunk strategy: {chunk_strategy_version}")

    output: list[DocumentChunk] = []
    global_index = 0
    for section in sections:
        split_chunks = _split_text(section.content, chunk_size, overlap)
        for section_chunk_index, content in enumerate(split_chunks):
            reason_codes = list(section.parser_capability.get("warnings") or [])
            if section.parser_capability.get("fallback_used"):
                reason_codes.append("fallback_parser_used")
            if section.metadata.get("raw_available") is False:
                reason_codes.append("source_path_missing_synthetic_fallback")
            reason_codes = sorted(set(reason_codes))
            chunk_id = stable_id(
                "chunk",
                section.source_fingerprint,
                section.section_id,
                section_chunk_index,
                chunk_strategy_version,
            )
            output.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=section.doc_id,
                    source_id=section.source_id,
                    section_id=section.section_id,
                    source_fingerprint=section.source_fingerprint,
                    asset_type=section.asset_type,
                    chunk_index=global_index,
                    section_chunk_index=section_chunk_index,
                    chunk_strategy_version=chunk_strategy_version,
                    parse_strategy_version=section.parse_strategy_version,
                    data_release_id=section.data_release_id,
                    doc_version=section.doc_version,
                    section_path=section.section_path,
                    section_type=section.section_type,
                    content=content,
                    page_no=section.page_no,
                    bbox=section.bbox,
                    parser_backend=section.parser_backend,
                    parser_capability=section.parser_capability,
                    reason_codes=reason_codes,
                )
            )
            global_index += 1
    return output

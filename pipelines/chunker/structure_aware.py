"""Structure-aware chunk planning for Week07.

This module keeps the classroom path deterministic: it does not call embedding
models or LLMs. It preserves section boundaries, prefers paragraph/sentence
breaks, and records character spans so downstream evidence can cite where a
chunk came from.
"""

from dataclasses import dataclass, field
import re


BOUNDARY_RE = re.compile(r"(?<=[。！？.!?])\s+|\n{2,}")
HARD_BOUNDARY_TYPES = {"table", "code", "image", "transcript"}


@dataclass(frozen=True)
class ChunkSlice:
    text: str
    span_start: int
    span_end: int
    heading_path: list[str] = field(default_factory=list)
    reason: str = "structure_aware"


def _heading_path(section_path: str | None) -> list[str]:
    if not section_path:
        return []
    return [part for part in re.split(r"\s*/\s*| > ", section_path) if part]


def _candidate_boundaries(text: str) -> list[int]:
    boundaries = {0, len(text)}
    for match in BOUNDARY_RE.finditer(text):
        boundaries.add(match.end())
    for match in re.finditer(r"\n[-*]\s+|\n\d+\.\s+", text):
        boundaries.add(match.start() + 1)
    return sorted(boundaries)


def split_section_text(
    text: str,
    *,
    section_path: str | None = None,
    section_type: str | None = None,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[ChunkSlice]:
    """Split one parsed section into chunk slices with original character spans."""

    stripped = text.strip()
    if not stripped:
        return []

    leading_offset = len(text) - len(text.lstrip())
    start_offset = leading_offset
    end_offset = leading_offset + len(stripped)
    path = _heading_path(section_path)

    if len(stripped) <= chunk_size or section_type in HARD_BOUNDARY_TYPES:
        return [
            ChunkSlice(
                text=stripped,
                span_start=start_offset,
                span_end=end_offset,
                heading_path=path,
                reason=f"whole_{section_type or 'section'}",
            )
        ]

    boundaries = _candidate_boundaries(stripped)
    output: list[ChunkSlice] = []
    local_start = 0

    while local_start < len(stripped):
        target_end = min(len(stripped), local_start + chunk_size)
        possible = [b for b in boundaries if local_start < b <= target_end]
        local_end = possible[-1] if possible else target_end
        if local_end <= local_start:
            local_end = target_end

        chunk_text = stripped[local_start:local_end].strip()
        if chunk_text:
            trim_left = len(stripped[local_start:local_end]) - len(stripped[local_start:local_end].lstrip())
            trim_right = len(stripped[local_start:local_end].rstrip())
            absolute_start = start_offset + local_start + trim_left
            absolute_end = start_offset + local_start + trim_right
            output.append(
                ChunkSlice(
                    text=chunk_text,
                    span_start=absolute_start,
                    span_end=absolute_end,
                    heading_path=path,
                    reason="boundary_split",
                )
            )

        if local_end >= len(stripped):
            break
        local_start = max(local_end - overlap, local_start + 1)

    return output

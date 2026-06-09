"""Optional Marker/Docling PDF parse adapters.

The Week07 deck positions Marker/Docling as the IDP production baseline. This
module keeps that route explicit without making those heavy packages mandatory
for student Docker/Podman runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedBlock:
    content: str
    section_type: str = "text"
    section_path: str = "body"
    page_no: int | None = None
    bbox: list[float] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class IdpParseResult:
    parser_backend: str
    blocks: list[ParsedBlock]
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def _markdown_blocks(markdown: str) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    current_heading = "body"
    for raw in markdown.split("\n\n"):
        text = raw.strip()
        if not text:
            continue
        if text.startswith("#"):
            heading = text.lstrip("#").strip() or "heading"
            current_heading = heading
            blocks.append(ParsedBlock(text, section_type="title", section_path=heading))
            continue
        section_type = "table" if text.startswith("|") and "\n|" in text else "text"
        blocks.append(ParsedBlock(text, section_type=section_type, section_path=current_heading))
    return blocks


def parse_with_marker(path: Path) -> IdpParseResult | None:
    try:
        from marker.converters.pdf import PdfConverter  # type: ignore
        from marker.models import create_model_dict  # type: ignore
    except Exception:
        return None

    converter = PdfConverter(artifact_dict=create_model_dict())
    rendered = converter(str(path))
    markdown = getattr(rendered, "markdown", "") or str(rendered)
    return IdpParseResult(
        parser_backend="marker",
        blocks=_markdown_blocks(markdown),
        metadata={"output_format": "markdown"},
    )


def parse_with_docling(path: Path) -> IdpParseResult | None:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except Exception:
        return None

    result = DocumentConverter().convert(str(path))
    doc = result.document
    blocks: list[ParsedBlock] = []
    for index, item in enumerate(doc.iterate_items()):
        content = ""
        if hasattr(item, "export_to_markdown"):
            content = item.export_to_markdown()
        elif hasattr(item, "text"):
            content = str(item.text)
        else:
            content = str(item)
        content = content.strip()
        if not content:
            continue
        type_name = type(item).__name__.lower()
        section_type = "table" if "table" in type_name else "image" if "picture" in type_name else "text"
        page_no = getattr(item, "page_no", None)
        bbox = None
        try:
            raw_bbox = item.prov[0].bbox if item.prov else None
            if raw_bbox:
                bbox = [raw_bbox.l, raw_bbox.t, raw_bbox.r, raw_bbox.b]
        except Exception:
            bbox = None
        blocks.append(
            ParsedBlock(
                content=content,
                section_type=section_type,
                section_path=f"docling/{section_type}/{index}",
                page_no=page_no,
                bbox=bbox,
            )
        )
    return IdpParseResult(parser_backend="docling", blocks=blocks, metadata={"output_format": "docling"})


def parse_pdf_with_idp(path: Path | None, preferred: tuple[str, ...] = ("marker", "docling")) -> IdpParseResult | None:
    if not path:
        return None
    for backend in preferred:
        if backend == "marker":
            result = parse_with_marker(path)
        elif backend == "docling":
            result = parse_with_docling(path)
        else:
            result = None
        if result and result.blocks:
            return result
    return None

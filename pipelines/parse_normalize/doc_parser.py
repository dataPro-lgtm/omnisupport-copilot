"""Document Parser — 文档解析、切片与证据链生成

支持两种解析后端（可配置切换）：
- Docling：结构保真，适合 PDF（保留表格/图像/坐标）
- Unstructured：适合 HTML/FAQ/Release Notes

每个解析结果输出统一的 ParsedSection 对象，后续统一切片与嵌入。

使用方式:
    python -m pipelines.parse_normalize.doc_parser \
        --source-id doc:workspace:000000000001 \
        --input-path /path/to/file.html \
        --asset-type html
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent

SectionType = Literal["text", "table", "image", "list", "title", "header"]
AssetType = Literal["pdf", "html", "faq", "release_notes", "api_doc", "community_post", "other"]


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class ParsedSection:
    """文档解析后的一个结构单元（段落/表格/图像等）"""
    source_id: str
    doc_id: str
    section_path: str           # 如 "安装指南 > 步骤 > 接线"
    section_type: SectionType
    content: str                # 文本内容（图像为描述/OCR）
    page_no: int | None = None
    bbox: str | None = None     # JSON [x0, y0, x1, y1]
    raw_html: str | None = None
    table_data: list | None = None   # 表格结构化数据
    image_path: str | None = None    # 图像 S3 路径
    section_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ParsedChunk:
    """切片后的检索单元，携带完整 evidence_anchor"""
    chunk_id: str
    doc_id: str
    source_id: str
    section_path: str
    section_type: SectionType
    content: str
    chunk_index: int
    page_no: int | None
    bbox: str | None
    # evidence_anchor 字段（直接内联，避免多表 join）
    source_url: str | None = None
    doc_version: str | None = None


# ── 解析后端：Docling ─────────────────────────────────────────────────────────

class DoclingParser:
    """
    使用 Docling 解析 PDF/Word 文档，保留结构层级与坐标。

    安装：pip install docling
    官方：https://github.com/docling-project/docling
    """

    def parse(self, file_path: Path, source_id: str, doc_id: str) -> list[ParsedSection]:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            logger.warning("Docling not installed, falling back to text-only extraction")
            return self._fallback_parse(file_path, source_id, doc_id)

        converter = DocumentConverter()
        result = converter.convert(str(file_path))
        doc = result.document

        sections: list[ParsedSection] = []
        for elem in doc.iterate_items():
            section_type = self._map_type(elem)
            content = self._extract_content(elem)
            if not content.strip():
                continue

            sections.append(ParsedSection(
                source_id=source_id,
                doc_id=doc_id,
                section_path=self._build_section_path(elem),
                section_type=section_type,
                content=content,
                page_no=getattr(elem, "page_no", None),
                bbox=self._extract_bbox(elem),
            ))

        return sections

    def _map_type(self, elem) -> SectionType:
        type_name = type(elem).__name__.lower()
        if "table" in type_name:
            return "table"
        if "picture" in type_name or "figure" in type_name:
            return "image"
        if "title" in type_name or "heading" in type_name:
            return "title"
        if "list" in type_name:
            return "list"
        return "text"

    def _extract_content(self, elem) -> str:
        if hasattr(elem, "export_to_markdown"):
            return elem.export_to_markdown()
        if hasattr(elem, "text"):
            return str(elem.text)
        return str(elem)

    def _build_section_path(self, elem) -> str:
        parts = []
        if hasattr(elem, "label"):
            parts.append(str(elem.label))
        return " > ".join(parts) if parts else "body"

    def _extract_bbox(self, elem) -> str | None:
        try:
            bbox = elem.prov[0].bbox if elem.prov else None
            if bbox:
                return json.dumps([bbox.l, bbox.t, bbox.r, bbox.b])
        except (AttributeError, IndexError):
            pass
        return None

    def _fallback_parse(self, file_path: Path, source_id: str, doc_id: str) -> list[ParsedSection]:
        """Docling 不可用时降级：按段落切分"""
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        sections = []
        for i, para in enumerate(text.split("\n\n")):
            para = para.strip()
            if len(para) < 20:
                continue
            sections.append(ParsedSection(
                source_id=source_id,
                doc_id=doc_id,
                section_path=f"para_{i}",
                section_type="text",
                content=para,
            ))
        return sections


# ── 解析后端：Unstructured ────────────────────────────────────────────────────

class UnstructuredParser:
    """
    使用 Unstructured 解析 HTML/FAQ/Release Notes，提取结构化元素。

    安装：pip install unstructured[html]
    官方：https://docs.unstructured.io
    """

    def parse(self, file_path: Path, source_id: str, doc_id: str) -> list[ParsedSection]:
        try:
            from unstructured.partition.auto import partition
            from unstructured.documents.elements import (
                Title, NarrativeText, Table, ListItem, Image, Header
            )
        except ImportError:
            logger.warning("Unstructured not installed, using fallback parser")
            return self._fallback_parse(file_path, source_id, doc_id)

        elements = partition(filename=str(file_path))
        sections: list[ParsedSection] = []
        breadcrumb: list[str] = []

        for elem in elements:
            text = str(elem).strip()
            if not text:
                continue

            if isinstance(elem, (Title, Header)):
                # 更新面包屑路径
                depth = getattr(elem.metadata, "category_depth", 0) or 0
                breadcrumb = breadcrumb[:depth] + [text]
                section_type = "title"
            elif isinstance(elem, Table):
                section_type = "table"
            elif isinstance(elem, ListItem):
                section_type = "list"
            elif isinstance(elem, Image):
                section_type = "image"
            else:
                section_type = "text"

            page_no = getattr(elem.metadata, "page_number", None)

            sections.append(ParsedSection(
                source_id=source_id,
                doc_id=doc_id,
                section_path=" > ".join(breadcrumb) if breadcrumb else "body",
                section_type=section_type,
                content=text,
                page_no=page_no,
            ))

        return sections

    def _fallback_parse(self, file_path: Path, source_id: str, doc_id: str) -> list[ParsedSection]:
        """降级：按换行切分"""
        try:
            from html.parser import HTMLParser

            class _StripHTML(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []

                def handle_data(self, data):
                    self.text_parts.append(data)

            p = _StripHTML()
            p.feed(file_path.read_text(encoding="utf-8", errors="ignore"))
            text = " ".join(p.text_parts)
        except Exception:
            text = file_path.read_text(encoding="utf-8", errors="ignore")

        sections = []
        for i, para in enumerate(text.split("\n\n")):
            para = para.strip()
            if len(para) < 20:
                continue
            sections.append(ParsedSection(
                source_id=source_id,
                doc_id=doc_id,
                section_path=f"para_{i}",
                section_type="text",
                content=para,
            ))
        return sections


# ── Chunker ───────────────────────────────────────────────────────────────────

class SlidingWindowChunker:
    """
    滑动窗口切分，保留 section_path 等证据锚点元数据。

    - chunk_size: 字符数（近似 token 数 * 4）
    - overlap: 窗口重叠字符数
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(
        self,
        section: ParsedSection,
        source_url: str | None = None,
        doc_version: str | None = None,
    ) -> list[ParsedChunk]:
        text = section.content
        if len(text) <= self.chunk_size:
            return [self._make_chunk(section, text, 0, source_url, doc_version)]

        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            chunks.append(self._make_chunk(section, chunk_text, idx, source_url, doc_version))
            idx += 1
            start = end - self.overlap
            if start >= len(text):
                break

        return chunks

    def _make_chunk(
        self,
        section: ParsedSection,
        text: str,
        idx: int,
        source_url: str | None,
        doc_version: str | None,
    ) -> ParsedChunk:
        chunk_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{section.source_id}:{section.section_id}:{idx}"
        ))
        return ParsedChunk(
            chunk_id=chunk_id,
            doc_id=section.doc_id,
            source_id=section.source_id,
            section_path=section.section_path,
            section_type=section.section_type,
            content=text.strip(),
            chunk_index=idx,
            page_no=section.page_no,
            bbox=section.bbox,
            source_url=source_url,
            doc_version=doc_version,
        )


# ── 解析主控 ─────────────────────────────────────────────────────────────────

class DocumentParseOrchestrator:
    """
    根据 asset_type 选择正确的解析后端，执行解析 + 切片 + DB 写入。
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self._docling = DoclingParser()
        self._unstructured = UnstructuredParser()
        self._chunker = SlidingWindowChunker(chunk_size, chunk_overlap)

    def select_parser(self, asset_type: AssetType):
        pdf_types = {"pdf"}
        html_types = {"html", "faq", "release_notes", "api_doc", "community_post", "other"}
        if asset_type in pdf_types:
            return self._docling
        return self._unstructured

    def parse_and_chunk(
        self,
        file_path: Path,
        source_id: str,
        doc_id: str,
        asset_type: AssetType,
        source_url: str | None = None,
        doc_version: str | None = None,
    ) -> list[ParsedChunk]:
        parser = self.select_parser(asset_type)
        sections = parser.parse(file_path, source_id, doc_id)

        all_chunks: list[ParsedChunk] = []
        for section in sections:
            chunks = self._chunker.chunk(section, source_url, doc_version)
            all_chunks.extend(chunks)

        logger.info(
            f"Parsed {source_id}: {len(sections)} sections → {len(all_chunks)} chunks "
            f"(backend: {type(parser).__name__})"
        )
        return all_chunks

    async def persist_chunks(self, conn, chunks: list[ParsedChunk], index_release_id: str = "index-v0.1.0"):
        """将 chunks 写入 knowledge_section 表（embedding 列 Week08 再填充）"""
        inserted = 0
        for chunk in chunks:
            try:
                await conn.execute(
                    """
                    INSERT INTO knowledge_section (
                        section_id, doc_id, source_id, section_path,
                        section_type, content, page_no, bbox,
                        chunk_index, index_release_id, created_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
                    ON CONFLICT (section_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        index_release_id = EXCLUDED.index_release_id
                    """,
                    chunk.chunk_id,
                    chunk.doc_id,
                    chunk.source_id,
                    chunk.section_path,
                    chunk.section_type,
                    chunk.content,
                    chunk.page_no,
                    chunk.bbox,
                    chunk.chunk_index,
                    index_release_id,
                )

                # 写 evidence_anchor
                await conn.execute(
                    """
                    INSERT INTO evidence_anchor (
                        chunk_id, source_id, source_url,
                        page_no, section_path, doc_version, modality
                    ) VALUES ($1,$2,$3,$4,$5,$6,'document')
                    ON CONFLICT DO NOTHING
                    """,
                    chunk.chunk_id,
                    chunk.source_id,
                    chunk.source_url,
                    chunk.page_no,
                    chunk.section_path,
                    chunk.doc_version,
                )
                inserted += 1
            except Exception as e:
                logger.error(f"Failed to insert chunk {chunk.chunk_id}: {e}")

        return inserted


# ── CLI ───────────────────────────────────────────────────────────────────────

async def _run_parse(source_id: str, input_path: Path, asset_type: str, dry_run: bool):
    import uuid as _uuid
    from pipelines.ingestion.db import acquire

    doc_id = str(_uuid.uuid5(_uuid.NAMESPACE_URL, source_id))
    orchestrator = DocumentParseOrchestrator()

    chunks = orchestrator.parse_and_chunk(
        file_path=input_path,
        source_id=source_id,
        doc_id=doc_id,
        asset_type=asset_type,
    )

    print(f"Parsed {len(chunks)} chunks from {input_path}")

    if dry_run:
        for c in chunks[:3]:
            print(f"  chunk[{c.chunk_index}] ({c.section_type}) [{c.section_path}]: {c.content[:80]}…")
        return

    async with acquire() as conn:
        inserted = await orchestrator.persist_chunks(conn, chunks)
        print(f"Inserted {inserted}/{len(chunks)} chunks to DB")


def main():
    parser = argparse.ArgumentParser(description="Document Parse Pipeline")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--input-path", type=Path, required=True)
    parser.add_argument("--asset-type", default="html",
                        choices=["pdf", "html", "faq", "release_notes", "api_doc", "other"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(_run_parse(args.source_id, args.input_path, args.asset_type, args.dry_run))


if __name__ == "__main__":
    main()

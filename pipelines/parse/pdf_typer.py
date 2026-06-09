"""PDF type detection for Week07 IDP routing.

The deck recommends choosing the parser by PDF type:
- text_based: IDP or lightweight text extractor can work.
- scanned: OCR-capable backend is required.
- hybrid: run text extraction plus OCR fallback.

PyMuPDF is used when available. The fallback uses pypdf text coverage so the
classroom image does not need another binary-heavy dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


@dataclass(frozen=True)
class PdfTypeReport:
    pdf_type: str
    page_count: int
    text_page_count: int
    text_coverage: float
    detector_backend: str
    recommended_route: str

    def to_dict(self) -> dict:
        return {
            "pdf_type": self.pdf_type,
            "page_count": self.page_count,
            "text_page_count": self.text_page_count,
            "text_coverage": self.text_coverage,
            "detector_backend": self.detector_backend,
            "recommended_route": self.recommended_route,
        }


def _classify(text_coverage: float) -> tuple[str, str]:
    if text_coverage > 0.8:
        return "text_based", "marker_or_docling"
    if text_coverage < 0.2:
        return "scanned", "mistral_ocr_or_ocr_idp"
    return "hybrid", "idp_plus_ocr_fallback"


def _detect_with_pymupdf(path: Path) -> PdfTypeReport | None:
    try:
        import fitz  # type: ignore
    except Exception:
        return None
    doc = fitz.open(str(path))
    page_count = len(doc)
    if page_count == 0:
        return PdfTypeReport("unknown", 0, 0, 0.0, "pymupdf", "manual_review")
    text_page_count = sum(1 for page in doc if page.get_text().strip())
    coverage = round(text_page_count / page_count, 4)
    pdf_type, route = _classify(coverage)
    return PdfTypeReport(pdf_type, page_count, text_page_count, coverage, "pymupdf", route)


def detect_pdf_type(path: Path | None = None, raw_bytes: bytes | None = None) -> PdfTypeReport:
    if path:
        report = _detect_with_pymupdf(path)
        if report:
            return report

    try:
        from pypdf import PdfReader
    except Exception:
        return PdfTypeReport("unknown", 0, 0, 0.0, "unavailable", "manual_review")

    if raw_bytes is not None:
        reader = PdfReader(BytesIO(raw_bytes))
    elif path:
        reader = PdfReader(str(path))
    else:
        return PdfTypeReport("unknown", 0, 0, 0.0, "pypdf", "manual_review")

    page_count = len(reader.pages)
    if page_count == 0:
        return PdfTypeReport("unknown", 0, 0, 0.0, "pypdf", "manual_review")
    text_page_count = sum(1 for page in reader.pages if (page.extract_text() or "").strip())
    coverage = round(text_page_count / page_count, 4)
    pdf_type, route = _classify(coverage)
    return PdfTypeReport(pdf_type, page_count, text_page_count, coverage, "pypdf", route)

"""Week07 parse/normalize CLI and core pipeline."""

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from pipelines.parse_normalize.chunking import chunk_sections
from pipelines.parse_normalize.evidence_anchor import build_evidence_anchors
from pipelines.parse_normalize.models import (
    DEFAULT_CHUNK_STRATEGY_VERSION,
    DEFAULT_PARSE_STRATEGY_VERSION,
    ParseArtifacts,
    ParseRunReport,
    SourceDocument,
    stable_id,
    utc_now_iso,
    write_json,
)
from pipelines.parse_normalize.parser_adapter import parse_documents
from pipelines.parse_normalize.quality_gate import QualityGateResult, evaluate_quality_gate
from pipelines.parse_normalize.raw_loader import load_sources
from pipelines.parse_normalize.reporting import write_quality_report_md, write_week8_ready_gate


def _default_parse_run_id(data_release_id: str, manifest_id: str | None) -> str:
    return stable_id("parse-run", data_release_id, manifest_id or "local", length=16)


def _jsonb(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


async def _ensure_week07_ppt_columns(conn) -> None:
    """Keep existing local Postgres volumes compatible with new Week07 fields."""

    await conn.execute(
        """
        ALTER TABLE knowledge_section
            ADD COLUMN IF NOT EXISTS span_start INT,
            ADD COLUMN IF NOT EXISTS span_end INT,
            ADD COLUMN IF NOT EXISTS heading_path JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS context_prefix TEXT
        """
    )
    await conn.execute(
        """
        ALTER TABLE evidence_anchor
            ADD COLUMN IF NOT EXISTS span_start INT,
            ADD COLUMN IF NOT EXISTS span_end INT,
            ADD COLUMN IF NOT EXISTS heading_path JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS retrieval_method TEXT,
            ADD COLUMN IF NOT EXISTS rerank_score DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION
        """
    )


async def _persist_to_db(
    *,
    documents: list[SourceDocument],
    sections: list[dict],
    chunks: list[dict],
    anchors: list[dict],
    parse_run: ParseRunReport,
    quality_samples: list[dict],
) -> None:
    from pipelines.ingestion.db import acquire

    parser_by_doc: dict[str, str] = {}
    capability_by_doc: dict[str, dict] = {}
    for section in sections:
        parser_by_doc.setdefault(section["doc_id"], section["parser_backend"])
        capability_by_doc.setdefault(section["doc_id"], section.get("parser_capability", {}))

    async with acquire() as conn:
        await _ensure_week07_ppt_columns(conn)
        async with conn.transaction():
            for document in documents:
                product_line = document.product_line
                if product_line == "unknown":
                    product_line = None
                await conn.execute(
                    """
                    INSERT INTO raw_doc_asset (
                        source_id, asset_type, raw_object_path, manifest_id, ingest_batch_id,
                        license_tag, product_line, doc_version, source_fingerprint, source_url,
                        pii_level, quality_gate
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'none',$11)
                    ON CONFLICT (source_id) DO UPDATE SET
                        source_fingerprint = EXCLUDED.source_fingerprint,
                        source_url = EXCLUDED.source_url,
                        quality_gate = EXCLUDED.quality_gate
                    """,
                    document.source_id,
                    document.asset_type,
                    document.source_url_or_path,
                    document.manifest_id,
                    document.batch_id,
                    document.license_tag,
                    product_line,
                    document.doc_version,
                    document.source_fingerprint,
                    document.source_url_or_path,
                    parse_run.quality_status,
                )
                await conn.execute(
                    """
                    INSERT INTO knowledge_doc (
                        doc_id, source_id, asset_type, product_line, doc_version, title,
                        source_url, source_fingerprint, license_tag, pii_level, quality_gate,
                        data_release_id, parse_strategy_version, parser_backend,
                        parser_capability, source_url_or_path, parse_run_id, parsed_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'none',$10,$11,$12,$13,$14::jsonb,$15,$16,NOW())
                    ON CONFLICT (doc_id) DO UPDATE SET
                        source_fingerprint = EXCLUDED.source_fingerprint,
                        data_release_id = EXCLUDED.data_release_id,
                        parse_strategy_version = EXCLUDED.parse_strategy_version,
                        parser_backend = EXCLUDED.parser_backend,
                        parser_capability = EXCLUDED.parser_capability,
                        parse_run_id = EXCLUDED.parse_run_id,
                        parsed_at = NOW()
                    """,
                    document.doc_id,
                    document.source_id,
                    document.asset_type,
                    product_line,
                    document.doc_version,
                    document.source_id,
                    document.source_url_or_path,
                    document.source_fingerprint,
                    document.license_tag,
                    parse_run.quality_status,
                    parse_run.data_release_id,
                    parse_run.parse_strategy_version,
                    parser_by_doc.get(document.doc_id, parse_run.parser),
                    _jsonb(capability_by_doc.get(document.doc_id, {})),
                    document.source_url_or_path,
                    parse_run.parse_run_id,
                )

            for chunk in chunks:
                await conn.execute(
                    """
                    INSERT INTO knowledge_section (
                        section_id, doc_id, source_id, section_path, section_type, content,
                        asset_type, page_no, bbox, chunk_index, data_release_id, chunk_strategy_version,
                        source_fingerprint, parse_strategy_version, parser_backend,
                        parser_capability, bbox_missing_reason, evidence_anchor_ids,
                        anchor_count, quality_status, allowed_for_indexing, reason_codes,
                        span_start, span_end, heading_path, context_prefix
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::jsonb,$17,$18,$19,$20,$21,$22,$23,$24,$25::jsonb,$26)
                    ON CONFLICT (section_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        asset_type = EXCLUDED.asset_type,
                        data_release_id = EXCLUDED.data_release_id,
                        chunk_strategy_version = EXCLUDED.chunk_strategy_version,
                        source_fingerprint = EXCLUDED.source_fingerprint,
                        parser_backend = EXCLUDED.parser_backend,
                        parser_capability = EXCLUDED.parser_capability,
                        evidence_anchor_ids = EXCLUDED.evidence_anchor_ids,
                        anchor_count = EXCLUDED.anchor_count,
                        quality_status = EXCLUDED.quality_status,
                        allowed_for_indexing = EXCLUDED.allowed_for_indexing,
                        span_start = EXCLUDED.span_start,
                        span_end = EXCLUDED.span_end,
                        heading_path = EXCLUDED.heading_path,
                        context_prefix = EXCLUDED.context_prefix
                    """,
                    chunk["chunk_id"],
                    chunk["doc_id"],
                    chunk["source_id"],
                    chunk.get("section_path"),
                    chunk.get("section_type"),
                    chunk["content"],
                    chunk["asset_type"],
                    chunk.get("page_no"),
                    None if chunk.get("bbox") is None else str(chunk.get("bbox")),
                    chunk["chunk_index"],
                    chunk["data_release_id"],
                    chunk["chunk_strategy_version"],
                    chunk["source_fingerprint"],
                    chunk["parse_strategy_version"],
                    chunk["parser_backend"],
                    _jsonb(chunk["parser_capability"]),
                    None,
                    chunk["evidence_anchor_ids"],
                    chunk["anchor_count"],
                    chunk["quality_status"],
                    chunk["allowed_for_indexing"],
                    chunk["reason_codes"],
                    chunk.get("span_start"),
                    chunk.get("span_end"),
                    _jsonb(chunk.get("heading_path", [])),
                    chunk.get("context_prefix"),
                )

            for anchor in anchors:
                modality = anchor["asset_type"]
                if modality in {"pdf", "html", "faq", "release_notes", "api_doc", "community_post", "other"}:
                    modality = "document"
                await conn.execute(
                    """
                    INSERT INTO evidence_anchor (
                        anchor_id, chunk_id, section_id, doc_id, source_id, source_fingerprint,
                        asset_type, anchor_type, source_url, source_url_or_path, section_path,
                        doc_version, page_no, bbox, bbox_missing_reason, parser_backend,
                        parser_capability, data_release_id, modality, start_ts, end_ts, metadata,
                        span_start, span_end, heading_path, retrieval_method, rerank_score, confidence
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17::jsonb,$18,$19,$20,$21,$22::jsonb,$23,$24,$25::jsonb,$26,$27,$28)
                    ON CONFLICT (anchor_id) DO UPDATE SET
                        source_fingerprint = EXCLUDED.source_fingerprint,
                        source_url_or_path = EXCLUDED.source_url_or_path,
                        parser_capability = EXCLUDED.parser_capability,
                        data_release_id = EXCLUDED.data_release_id,
                        metadata = EXCLUDED.metadata,
                        span_start = EXCLUDED.span_start,
                        span_end = EXCLUDED.span_end,
                        heading_path = EXCLUDED.heading_path,
                        retrieval_method = EXCLUDED.retrieval_method,
                        rerank_score = EXCLUDED.rerank_score,
                        confidence = EXCLUDED.confidence
                    """,
                    anchor["anchor_id"],
                    anchor["chunk_id"],
                    anchor["section_id"],
                    anchor["doc_id"],
                    anchor["source_id"],
                    anchor["source_fingerprint"],
                    anchor["asset_type"],
                    anchor["anchor_type"],
                    anchor["source_url_or_path"],
                    anchor["source_url_or_path"],
                    anchor["section_path"],
                    anchor["doc_version"],
                    anchor["page_no"],
                    None if anchor.get("bbox") is None else str(anchor.get("bbox")),
                    anchor.get("bbox_missing_reason"),
                    anchor["parser_backend"],
                    _jsonb(anchor.get("parser_capability", {})),
                    anchor["data_release_id"],
                    modality,
                    anchor.get("start_ts"),
                    anchor.get("end_ts"),
                    _jsonb(anchor.get("metadata", {})),
                    anchor.get("span_start"),
                    anchor.get("span_end"),
                    _jsonb(anchor.get("heading_path", [])),
                    anchor.get("retrieval_method"),
                    anchor.get("rerank_score"),
                    anchor.get("confidence"),
                )

            await conn.execute(
                """
                INSERT INTO document_parse_run (
                    parse_run_id, status, manifest_id, batch_id, parser, chunk_strategy_version,
                    parse_strategy_version, data_release_id, started_at, finished_at,
                    source_count, section_count, chunk_count, anchor_count, quality_status,
                    week8_ready, warnings, errors, artifacts
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::text::timestamptz,$10::text::timestamptz,$11,$12,$13,$14,$15,$16,$17::jsonb,$18::jsonb,$19::jsonb)
                ON CONFLICT (parse_run_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    quality_status = EXCLUDED.quality_status,
                    week8_ready = EXCLUDED.week8_ready,
                    warnings = EXCLUDED.warnings,
                    errors = EXCLUDED.errors,
                    artifacts = EXCLUDED.artifacts
                """,
                parse_run.parse_run_id,
                parse_run.status,
                parse_run.manifest_id,
                parse_run.batch_id,
                parse_run.parser,
                parse_run.chunk_strategy_version,
                parse_run.parse_strategy_version,
                parse_run.data_release_id,
                parse_run.started_at,
                parse_run.finished_at,
                parse_run.source_count,
                parse_run.section_count,
                parse_run.chunk_count,
                parse_run.anchor_count,
                parse_run.quality_status,
                parse_run.week8_ready,
                _jsonb(parse_run.warnings),
                _jsonb(parse_run.errors),
                _jsonb(parse_run.artifacts),
            )

            for sample in quality_samples:
                await conn.execute(
                    """
                    INSERT INTO chunk_quality_sample (
                        sample_id, chunk_id, section_id, status, reason_codes, checks
                    ) VALUES ($1,$2,$3,$4,$5,$6::jsonb)
                    ON CONFLICT (sample_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        reason_codes = EXCLUDED.reason_codes,
                        checks = EXCLUDED.checks
                    """,
                    sample["sample_id"],
                    sample["chunk_id"],
                    sample["section_id"],
                    sample["status"],
                    sample["reason_codes"],
                    _jsonb(sample["checks"]),
                )


def run_parse_pipeline(
    *,
    manifest_path: Path | None,
    source_id: str | None = None,
    input_path: Path | None = None,
    content_type: str | None = None,
    parser: str = "auto",
    chunk_strategy_version: str = DEFAULT_CHUNK_STRATEGY_VERSION,
    data_release_id: str = "week07-dev-local",
    parse_strategy_version: str = DEFAULT_PARSE_STRATEGY_VERSION,
    expected_fingerprint: str | None = None,
    dry_run: bool = True,
    artifacts_dir: Path = Path("artifacts/week07"),
    report_json: Path | None = Path("reports/week07/parse_run_report.json"),
    quality_report_md: Path | None = Path("reports/week07/chunk_quality_report.md"),
    week8_gate_json: Path | None = Path("reports/week07/week8_ready_gate.json"),
) -> tuple[ParseRunReport, QualityGateResult]:
    started_at = utc_now_iso()
    manifest, documents = load_sources(
        manifest_path=manifest_path,
        source_id=source_id,
        input_path=input_path,
        content_type=content_type,
        data_release_id=data_release_id,
        expected_fingerprint=expected_fingerprint,
    )
    sections = parse_documents(
        documents,
        parser=parser,
        parse_strategy_version=parse_strategy_version,
    )
    chunks = chunk_sections(
        sections,
        chunk_strategy_version=chunk_strategy_version,
        chunk_size=int(manifest.get("ingest_config", {}).get("chunk_size") or 512),
        overlap=int(manifest.get("ingest_config", {}).get("chunk_overlap") or 64),
    )
    anchors = build_evidence_anchors(sections, chunks)
    gate = evaluate_quality_gate(sections, chunks, anchors)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ParseArtifacts(
        sections=str(artifacts_dir / "sections.json"),
        chunks=str(artifacts_dir / "chunks.json"),
        evidence_anchors=str(artifacts_dir / "evidence_anchors.json"),
        quality_samples=str(artifacts_dir / "chunk_quality_samples.json"),
    )
    sections_payload = [section.to_dict() for section in sections]
    chunks_payload = [chunk.to_dict() for chunk in chunks]
    anchors_payload = [anchor.to_dict() for anchor in anchors]
    write_json(Path(artifacts.sections), sections_payload)
    write_json(Path(artifacts.chunks), chunks_payload)
    write_json(Path(artifacts.evidence_anchors), anchors_payload)
    write_json(Path(artifacts.quality_samples), gate.samples)

    status = "failed" if gate.errors else "warn" if gate.warnings else "success"
    parser_warnings = [
        warning
        for section in sections
        for warning in section.parser_capability.get("warnings", [])
    ]
    warnings = sorted(set(gate.warnings + parser_warnings + [w for document in documents for w in document.warnings]))
    parse_run = ParseRunReport(
        parse_run_id=_default_parse_run_id(data_release_id, manifest.get("manifest_id")),
        status=status,
        manifest_id=manifest.get("manifest_id"),
        batch_id=manifest.get("batch_id"),
        parser=parser,
        chunk_strategy_version=chunk_strategy_version,
        parse_strategy_version=parse_strategy_version,
        data_release_id=data_release_id,
        started_at=started_at,
        finished_at=utc_now_iso(),
        source_count=len(documents),
        section_count=len(sections),
        chunk_count=len(chunks),
        anchor_count=len(anchors),
        quality_status=gate.quality_status,
        week8_ready=gate.week8_ready,
        warnings=warnings,
        errors=gate.errors,
        artifacts=artifacts.to_dict(),
    )

    if report_json:
        write_json(report_json, parse_run.to_dict())
    if quality_report_md:
        write_quality_report_md(quality_report_md, gate=gate, parse_run=parse_run)
    if week8_gate_json:
        write_week8_ready_gate(week8_gate_json, gate, parse_run)

    if not dry_run:
        asyncio.run(
            _persist_to_db(
                documents=documents,
                sections=sections_payload,
                chunks=chunks_payload,
                anchors=anchors_payload,
                parse_run=parse_run,
                quality_samples=gate.samples,
            )
        )

    return parse_run, gate


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Week07 document parse/normalize pipeline")
    parser.add_argument("--manifest-path", type=Path)
    parser.add_argument("--source-id")
    parser.add_argument("--doc-id", help="Accepted for classroom compatibility; doc_id is derived.")
    parser.add_argument("--input-path", type=Path)
    parser.add_argument("--source-dir", type=Path, help="Reserved for instructor-scale raw-file mapping.")
    parser.add_argument("--content-type")
    parser.add_argument(
        "--parser",
        choices=[
            "auto",
            "idp",
            "marker",
            "docling",
            "unstructured",
            "pypdf",
            "pypdf_baseline",
            "ocr",
            "media",
            "fallback",
        ],
        default="auto",
    )
    parser.add_argument("--chunk-strategy", default=DEFAULT_CHUNK_STRATEGY_VERSION)
    parser.add_argument("--data-release-id", default="week07-dev-local")
    parser.add_argument("--parse-strategy-version", default=DEFAULT_PARSE_STRATEGY_VERSION)
    parser.add_argument("--expected-fingerprint")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--artifacts-dir", type=Path, default=Path("artifacts/week07"))
    parser.add_argument("--report-json", type=Path, default=Path("reports/week07/parse_run_report.json"))
    parser.add_argument("--quality-report-md", type=Path, default=Path("reports/week07/chunk_quality_report.md"))
    parser.add_argument("--week8-gate-json", type=Path, default=Path("reports/week07/week8_ready_gate.json"))
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    parse_run, gate = run_parse_pipeline(
        manifest_path=args.manifest_path,
        source_id=args.source_id,
        input_path=args.input_path,
        content_type=args.content_type,
        parser=args.parser,
        chunk_strategy_version=args.chunk_strategy,
        data_release_id=args.data_release_id,
        parse_strategy_version=args.parse_strategy_version,
        expected_fingerprint=args.expected_fingerprint,
        dry_run=args.dry_run,
        artifacts_dir=args.artifacts_dir,
        report_json=args.report_json,
        quality_report_md=args.quality_report_md,
        week8_gate_json=args.week8_gate_json,
    )
    print(
        f"{parse_run.parse_run_id}: status={parse_run.status}, "
        f"sections={parse_run.section_count}, chunks={parse_run.chunk_count}, "
        f"anchors={parse_run.anchor_count}, week8_ready={gate.week8_ready}"
    )


if __name__ == "__main__":
    main()

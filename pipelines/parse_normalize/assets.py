"""Dagster assets for the Week07 parse/normalize layer."""

import json
import os
from pathlib import Path

from dagster import AssetExecutionContext, MetadataValue, Output, asset

from pipelines.parse_normalize.run_parse import run_parse_pipeline


def _week07_manifest_path() -> Path:
    return Path(
        os.environ.get(
            "WEEK07_MANIFEST_PATH",
            "data/seed_manifests/manifest_workspace_helpcenter_v1.json",
        )
    )


def _week07_artifacts_dir() -> Path:
    return Path(os.environ.get("WEEK07_ARTIFACTS_DIR", "artifacts/week07"))


def _week07_report_dir() -> Path:
    return Path(os.environ.get("WEEK07_REPORT_DIR", "reports/week07"))


def _read_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else []


@asset(
    group_name="parse_normalize",
    deps=["raw_doc_assets"],
    description="解析文档资产，提取 section/table/image/page 结构，生成 knowledge_section 记录",
    tags={"layer": "silver", "modality": "document"},
)
def parsed_doc_sections(
    context: AssetExecutionContext,
    raw_doc_assets: list[dict],
) -> Output[list[dict]]:
    """
    文档解析 → knowledge_section。

    Thin wrapper over `run_parse_pipeline`. The CLI remains the primary
    classroom path; Dagster observes the same artifacts instead of maintaining a
    second parser implementation.
    """
    report_dir = _week07_report_dir()
    parse_run, gate = run_parse_pipeline(
        manifest_path=_week07_manifest_path(),
        parser=os.environ.get("WEEK07_PARSER", "auto"),
        chunk_strategy_version=os.environ.get("WEEK07_CHUNK_STRATEGY_VERSION", "section_aware_v1"),
        data_release_id=os.environ.get("WEEK07_DATA_RELEASE_ID", "week07-dev-local"),
        dry_run=os.environ.get("WEEK07_PARSE_DRY_RUN", "true").lower() == "true",
        artifacts_dir=_week07_artifacts_dir(),
        report_json=report_dir / "parse_run_report.json",
        quality_report_md=report_dir / "chunk_quality_report.md",
        week8_gate_json=report_dir / "week8_ready_gate.json",
    )
    sections = _read_json(Path(parse_run.artifacts["sections"]))

    context.log.info(
        "Week07 parsed %s documents into %s sections",
        len(raw_doc_assets),
        len(sections),
    )

    return Output(
        sections,
        metadata={
            "section_count": MetadataValue.int(len(sections)),
            "chunk_count": MetadataValue.int(parse_run.chunk_count),
            "quality_status": MetadataValue.text(parse_run.quality_status),
            "week8_ready": MetadataValue.bool(gate.week8_ready),
            "parse_run_id": MetadataValue.text(parse_run.parse_run_id),
            "report_path": MetadataValue.text(str(report_dir / "parse_run_report.json")),
        },
    )


@asset(
    group_name="parse_normalize",
    deps=["parsed_doc_sections"],
    description="将 section 切分为检索 chunk，生成 evidence_anchor，准备写入向量索引",
    tags={"layer": "silver", "modality": "document"},
)
def knowledge_chunks(
    context: AssetExecutionContext,
    parsed_doc_sections: list[dict],
) -> Output[list[dict]]:
    """
    Chunk 切分 + EvidenceAnchor 生成。

    Reads the chunk artifact emitted by `parsed_doc_sections`. Week08 owns
    embeddings and pgvector writes; Week07 only marks indexing eligibility.
    """
    chunk_path = _week07_artifacts_dir() / "chunks.json"
    chunks = _read_json(chunk_path)
    allowed = sum(1 for chunk in chunks if chunk.get("allowed_for_indexing"))
    context.log.info("Week07 loaded %s chunks; %s allowed for Week08 indexing", len(chunks), allowed)

    return Output(
        chunks,
        metadata={
            "section_count": MetadataValue.int(len(parsed_doc_sections)),
            "chunk_count": MetadataValue.int(len(chunks)),
            "allowed_for_indexing_count": MetadataValue.int(allowed),
            "artifact_path": MetadataValue.text(str(chunk_path)),
        },
    )


@asset(
    group_name="parse_normalize",
    deps=["raw_ticket_events"],
    description="将原始工单事件规范化为 ticket_fact Silver 表记录",
    tags={"layer": "silver", "modality": "structured"},
)
def ticket_facts(
    context: AssetExecutionContext,
    raw_ticket_events: list[dict],
) -> Output[list[dict]]:
    """
    工单规范化 → ticket_fact Silver 层。

    Week01: 骨架占位。
    Week03: 接入真实 ticket simulator 数据，写入 PostgreSQL ticket_fact 表。
    Week04: 写入 Iceberg Silver 表，支持 time travel。
    """
    facts = []

    for event_source in raw_ticket_events:
        # TODO(Week03): 读取 JSONL 文件，逐条规范化
        # 每条记录对应 ticket_contract.json schema
        context.log.debug(f"[stub] Would normalize: {event_source['source_id']}")

    context.log.info(f"[Week01 stub] ticket_facts: 0 facts (接入 Week03)")

    return Output(
        facts,
        metadata={
            "fact_count": MetadataValue.int(0),
            "stub": MetadataValue.bool(True),
        },
    )

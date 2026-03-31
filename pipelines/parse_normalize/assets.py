"""Dagster 资产定义 — 解析与规范化层

Week01 骨架：定义解析资产的接口与元数据契约。
Week07 起接入真实 Docling/Unstructured 文档解析、Whisper ASR、FFmpeg 视频切片。
"""

from dagster import asset, AssetExecutionContext, MetadataValue, Output
from typing import Any


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

    Week01: 骨架占位，输出空列表。
    Week07: 接入 Docling/Unstructured，保留页码/段落/表格/图像/坐标。
    """
    sections = []

    for doc in raw_doc_assets:
        # TODO(Week07): 调用 Docling 或 Unstructured 解析
        # 解析结果应包含：
        #   - section_id, doc_source_id, section_path, content
        #   - page_no, bbox, section_type (text/table/image)
        #   - source_fingerprint, doc_version
        context.log.debug(f"[stub] Would parse: {doc['source_id']}")

    context.log.info(f"[Week01 stub] parsed_doc_sections: 0 sections (接入 Week07)")

    return Output(
        sections,
        metadata={
            "section_count": MetadataValue.int(0),
            "stub": MetadataValue.bool(True),
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

    Week01: 骨架占位。
    Week07-08: 实现滑动窗口切分 + pgvector 嵌入写入。
    """
    chunks = []

    for section in parsed_doc_sections:
        # TODO(Week07): 滑动窗口切分
        # TODO(Week08): 嵌入生成 + pgvector 写入
        # 每个 chunk 必须包含 evidence_anchor:
        #   source_id, source_url, page_no, section_path, doc_version
        pass

    context.log.info(f"[Week01 stub] knowledge_chunks: 0 chunks (接入 Week07-08)")

    return Output(
        chunks,
        metadata={
            "chunk_count": MetadataValue.int(0),
            "stub": MetadataValue.bool(True),
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

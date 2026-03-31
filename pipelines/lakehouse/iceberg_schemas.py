"""Apache Iceberg 表 Schema 定义

三层设计：Bronze（保真落盘）/ Silver（规范化）/ Gold（服务消费）

Week01: 定义 schema 目标形态，作为实施合同。
Week04: 使用 PyIceberg 在 MinIO 上真实建表。
"""

from typing import Any


# ── Bronze 层 ─────────────────────────────────────────────────────────────────
# 设计原则：保真落盘，不做过早业务解释，保留 source_fingerprint

BRONZE_SCHEMAS: dict[str, dict[str, Any]] = {
    "raw_ticket_event": {
        "description": "工单原始事件流，保真落盘",
        "fields": [
            ("event_id", "string", "NOT NULL"),
            ("source_id", "string", "NOT NULL"),
            ("manifest_id", "string", ""),
            ("ingest_batch_id", "string", ""),
            ("raw_payload", "string", "JSON 原始内容"),
            ("schema_version", "string", ""),
            ("license_tag", "string", ""),
            ("pii_level", "string", ""),
            ("ingest_ts", "timestamp", ""),
            ("source_fingerprint", "string", "SHA-256"),
        ],
        "partition_spec": [("ingest_ts", "day")],
        "sort_order": [("ingest_ts", "asc")],
    },
    "raw_doc_asset": {
        "description": "文档资产原始记录，包含原始对象路径与元数据",
        "fields": [
            ("source_id", "string", "NOT NULL"),
            ("asset_type", "string", "pdf/html/faq etc."),
            ("raw_object_path", "string", "s3://..."),
            ("manifest_id", "string", ""),
            ("ingest_batch_id", "string", ""),
            ("license_tag", "string", ""),
            ("product_line", "string", ""),
            ("doc_version", "string", ""),
            ("page_count", "int", ""),
            ("source_fingerprint", "string", "SHA-256"),
            ("pii_level", "string", ""),
            ("quality_gate", "string", ""),
            ("ingest_ts", "timestamp", ""),
        ],
        "partition_spec": [("product_line", "identity"), ("ingest_ts", "month")],
    },
    "raw_audio_asset": {
        "description": "音频资产原始记录（含 TTS 合成）",
        "fields": [
            ("call_id", "string", "NOT NULL"),
            ("source_id", "string", ""),
            ("audio_type", "string", "real_call/tts_synthetic/..."),
            ("duration_sec", "double", ""),
            ("raw_object_path", "string", "可能为 null（不可分发音频）"),
            ("transcript_object_path", "string", ""),
            ("speaker_count", "int", ""),
            ("diarization_available", "boolean", ""),
            ("asr_confidence", "double", ""),
            ("pii_level", "string", ""),
            ("pii_redacted", "boolean", ""),
            ("license_tag", "string", ""),
            ("ingest_ts", "timestamp", ""),
        ],
        "partition_spec": [("ingest_ts", "month")],
    },
    "raw_video_asset": {
        "description": "视频资产原始记录",
        "fields": [
            ("video_id", "string", "NOT NULL"),
            ("source_id", "string", ""),
            ("video_type", "string", ""),
            ("duration_sec", "double", ""),
            ("raw_object_path", "string", ""),
            ("transcript_object_path", "string", ""),
            ("keyframes_prefix", "string", ""),
            ("segment_count", "int", ""),
            ("has_ocr", "boolean", ""),
            ("has_caption", "boolean", ""),
            ("license_tag", "string", ""),
            ("pii_level", "string", ""),
            ("ingest_ts", "timestamp", ""),
        ],
        "partition_spec": [("ingest_ts", "month")],
    },
    "raw_transcript_segment": {
        "description": "音频/视频转写片段，utterance 粒度",
        "fields": [
            ("segment_id", "string", "NOT NULL"),
            ("call_id_or_video_id", "string", ""),
            ("modality", "string", "audio/video"),
            ("speaker_role", "string", "agent/customer/narrator"),
            ("start_ts", "double", "秒"),
            ("end_ts", "double", "秒"),
            ("text", "string", ""),
            ("confidence", "double", ""),
            ("pii_redaction_flag", "boolean", ""),
        ],
        "partition_spec": [("modality", "identity")],
    },
}


# ── Silver 层 ─────────────────────────────────────────────────────────────────
# 设计原则：统一 schema，可追溯，可演化

SILVER_SCHEMAS: dict[str, dict[str, Any]] = {
    "ticket_fact": {
        "description": "规范化工单事实表",
        "fields": [
            ("ticket_id", "string", "NOT NULL PK"),
            ("customer_id", "string", "FK customer_dim"),
            ("org_id", "string", "FK entitlement_dim"),
            ("status", "string", ""),
            ("priority", "string", ""),
            ("category", "string", ""),
            ("product_line", "string", ""),
            ("product_version", "string", ""),
            ("subject", "string", ""),
            ("error_codes", "list<string>", ""),
            ("asset_ids", "list<string>", ""),
            ("assignee_id", "string", ""),
            ("sla_tier", "string", ""),
            ("sla_due_at", "timestamp", ""),
            ("created_at", "timestamp", ""),
            ("updated_at", "timestamp", ""),
            ("resolved_at", "timestamp", ""),
            ("pii_level", "string", ""),
            ("pii_redacted", "boolean", ""),
            ("data_release_id", "string", "版本追踪"),
            ("ingest_batch_id", "string", ""),
        ],
        "partition_spec": [("product_line", "identity"), ("created_at", "month")],
        "sort_order": [("created_at", "desc")],
    },
    "knowledge_doc": {
        "description": "知识文档资产表（规范化后）",
        "fields": [
            ("doc_id", "string", "NOT NULL PK"),
            ("source_id", "string", "关联 raw_doc_asset"),
            ("asset_type", "string", ""),
            ("product_line", "string", ""),
            ("doc_version", "string", ""),
            ("title", "string", ""),
            ("language", "string", ""),
            ("page_count", "int", ""),
            ("section_count", "int", ""),
            ("chunk_count", "int", ""),
            ("source_url", "string", ""),
            ("source_fingerprint", "string", ""),
            ("license_tag", "string", ""),
            ("pii_level", "string", ""),
            ("quality_gate", "string", ""),
            ("data_release_id", "string", ""),
            ("indexed_at", "timestamp", "写入向量索引的时间"),
        ],
        "partition_spec": [("product_line", "identity")],
    },
    "knowledge_section": {
        "description": "文档 section/chunk 粒度，含证据锚点字段",
        "fields": [
            ("section_id", "string", "NOT NULL PK"),
            ("doc_id", "string", "FK knowledge_doc"),
            ("source_id", "string", ""),
            ("section_path", "string", "标题路径，如 '安装 > 步骤 > 接线'"),
            ("section_type", "string", "text/table/image/list"),
            ("content", "string", "chunk 文本内容"),
            ("page_no", "int", ""),
            ("bbox", "string", "坐标 JSON，如 '[x0,y0,x1,y1]'"),
            ("chunk_index", "int", "同一 section 内的切分序号"),
            ("embedding_model", "string", "嵌入模型标识"),
            ("embedding_dim", "int", ""),
            ("data_release_id", "string", ""),
            ("index_release_id", "string", ""),
        ],
        "partition_spec": [("doc_id", "bucket[100]")],
    },
    "evidence_anchor": {
        "description": "证据锚点表，连接生成答案与知识源",
        "fields": [
            ("anchor_id", "string", "NOT NULL PK"),
            ("chunk_id", "string", "FK knowledge_section"),
            ("source_id", "string", ""),
            ("source_url", "string", ""),
            ("page_no", "int", ""),
            ("section_path", "string", ""),
            ("doc_version", "string", ""),
            ("modality", "string", "document/audio/video"),
            ("start_ts", "double", "音视频起始秒，文档为 null"),
            ("end_ts", "double", ""),
            ("created_at", "timestamp", ""),
        ],
    },
    "transcript_segment": {
        "description": "规范化转写片段 Silver 层",
        "fields": [
            ("segment_id", "string", "NOT NULL PK"),
            ("media_id", "string", "call_id or video_id"),
            ("modality", "string", "audio/video"),
            ("speaker_role", "string", ""),
            ("start_ts", "double", ""),
            ("end_ts", "double", ""),
            ("text", "string", "脱敏后文本"),
            ("confidence", "double", ""),
            ("ticket_id", "string", "关联工单（若有）"),
            ("data_release_id", "string", ""),
        ],
        "partition_spec": [("modality", "identity")],
    },
}


# ── Gold 层 ───────────────────────────────────────────────────────────────────
# 设计原则：供检索、查询、工具调用与 KPI 展示消费

GOLD_SCHEMAS: dict[str, dict[str, Any]] = {
    "support_case_mart": {
        "description": "支持案例宽表，联合 ticket + customer + entitlement",
        "fields": [
            ("ticket_id", "string", ""),
            ("customer_name", "string", ""),
            ("org_name", "string", ""),
            ("sla_tier", "string", ""),
            ("status", "string", ""),
            ("priority", "string", ""),
            ("category", "string", ""),
            ("product_line", "string", ""),
            ("resolution_hours", "double", "解决耗时"),
            ("sla_breached", "boolean", ""),
            ("created_at", "timestamp", ""),
        ],
    },
    "support_kpi_mart": {
        "description": "支持 KPI 汇总表，供 query_kpi 工具消费",
        "fields": [
            ("kpi_date", "date", ""),
            ("product_line", "string", ""),
            ("sla_tier", "string", ""),
            ("open_tickets", "int", ""),
            ("resolved_tickets", "int", ""),
            ("avg_resolution_hours", "double", ""),
            ("sla_compliance_rate", "double", ""),
            ("p1_count", "int", ""),
            ("p2_count", "int", ""),
        ],
        "partition_spec": [("kpi_date", "month")],
    },
    "kb_serving_asset": {
        "description": "知识库检索服务视图，含最新 index_release_id 的 chunk",
        "fields": [
            ("chunk_id", "string", ""),
            ("doc_id", "string", ""),
            ("product_line", "string", ""),
            ("content", "string", ""),
            ("section_path", "string", ""),
            ("page_no", "int", ""),
            ("source_url", "string", ""),
            ("doc_version", "string", ""),
            ("index_release_id", "string", ""),
            ("embedding_model", "string", ""),
        ],
    },
    "agent_tool_input_view": {
        "description": "Agent 工具调用输入视图，预计算允许的工具动作列表",
        "fields": [
            ("org_id", "string", ""),
            ("sla_tier", "string", ""),
            ("allowed_tools", "list<string>", ""),
            ("max_ticket_priority", "string", ""),
            ("hitl_required_for", "list<string>", ""),
        ],
    },
}


def print_schema_summary():
    """打印所有表的 schema 摘要，用于验收检查"""
    for layer, schemas in [
        ("BRONZE", BRONZE_SCHEMAS),
        ("SILVER", SILVER_SCHEMAS),
        ("GOLD", GOLD_SCHEMAS),
    ]:
        print(f"\n{'='*60}")
        print(f"  {layer} LAYER ({len(schemas)} tables)")
        print(f"{'='*60}")
        for table_name, schema in schemas.items():
            field_count = len(schema.get("fields", []))
            print(f"  {table_name} ({field_count} fields) — {schema['description']}")


if __name__ == "__main__":
    print_schema_summary()

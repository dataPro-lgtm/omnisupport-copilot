"""RAG API 请求/响应 Pydantic 模型

遵循 RAG Response Contract v1（见 contracts/service/）。
所有响应必须携带 citations、evidence_ids、trace_id、release_id。
"""

from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ── 证据锚点 ─────────────────────────────────────────────────────────────────

class EvidenceAnchor(BaseModel):
    """单条证据的源头引用，可追溯到具体文档位置"""
    source_id: str
    source_url: Optional[str] = None
    page_no: Optional[int] = None
    section_path: Optional[str] = None
    doc_version: Optional[str] = None
    modality: Literal["document", "audio", "video"] = "document"
    start_ts: Optional[float] = None   # 音视频起始时间戳（秒）
    end_ts: Optional[float] = None     # 音视频结束时间戳（秒）


# ── 检索结果片段 ─────────────────────────────────────────────────────────────

class RetrievedChunk(BaseModel):
    chunk_id: str
    content: str
    score: float = Field(ge=0.0, le=1.0)
    rerank_score: Optional[float] = None
    evidence_anchor: EvidenceAnchor


# ── 查询请求 ──────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """RAG 查询请求"""
    query: str = Field(..., min_length=1, max_length=2048, description="用户问题")
    product_line: Optional[Literal[
        "northstar_workspace",
        "northstar_edge_gateway",
        "northstar_studio",
        "any"
    ]] = "any"
    modalities: List[Literal["document", "audio", "video"]] = ["document"]
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.6, ge=0.0, le=1.0)
    session_id: Optional[str] = None
    idempotency_key: Optional[str] = None


# ── 查询响应 ──────────────────────────────────────────────────────────────────

class QueryResponse(BaseModel):
    """RAG 查询响应 — 符合 RAG Response Contract v1"""
    answer: str
    citations: List[str] = Field(
        description="可读引用列表，如 '[文档名, 第N页]'"
    )
    evidence_ids: List[str] = Field(
        description="chunk_id 列表，用于审计追踪"
    )
    retrieved_chunks: List[RetrievedChunk] = Field(
        description="原始检索结果，用于调试"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    answer_grounded: bool = Field(
        description="答案是否有证据支撑（confidence >= min_score）"
    )
    release_id: str
    trace_id: str
    session_id: Optional[str] = None


# ── 健康检查 ──────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    service: str
    version: str
    release_id: str
    checks: dict


# ── 管理接口 ──────────────────────────────────────────────────────────────────

class ReleaseInfoResponse(BaseModel):
    release_id: str
    data_release_id: str
    index_release_id: str
    prompt_release_id: str

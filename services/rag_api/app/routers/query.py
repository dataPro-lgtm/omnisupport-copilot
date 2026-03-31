"""RAG 查询端点 v1 — 接入真实检索 + Claude 生成

链路：
  请求 → embed query → vector_search + fts_search → RRF → rerank
        → Claude generate → 证据引用 → 审计日志 → 响应
"""

import uuid
import logging
from typing import AsyncGenerator

import asyncpg
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from opentelemetry import trace

from app.models.rag_models import QueryRequest, QueryResponse, RetrievedChunk, EvidenceAnchor
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["rag"])
tracer = trace.get_tracer(__name__)

# ── DB 连接池（懒初始化）─────────────────────────────────────────────────────

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    return _pool


# ── 主查询端点 ────────────────────────────────────────────────────────────────

@router.post(
    "/query",
    response_model=QueryResponse,
    summary="RAG 知识查询",
    description="""
    对 OmniSupport 知识库执行混合检索并用 Claude 生成带证据引用的回答。

    检索链路：pgvector ANN + PostgreSQL FTS → RRF 融合 → Cross-Encoder 精排

    所有响应携带 `trace_id` 和 `release_id`，支持审计追踪与回滚。
    置信度低于 `min_score` 时 `answer_grounded=false`。
    """,
)
async def query_knowledge(
    request: QueryRequest,
    http_request: Request,
) -> QueryResponse:
    trace_id = getattr(http_request.state, "request_id", str(uuid.uuid4()))

    with tracer.start_as_current_span("rag.query") as span:
        span.set_attribute("omni.query_length", len(request.query))
        span.set_attribute("omni.product_line", request.product_line or "any")
        span.set_attribute("omni.trace_id", trace_id)
        span.set_attribute("omni.release_id", settings.release_id)

        # ── 检索 ─────────────────────────────────────────────────────────────
        with tracer.start_as_current_span("rag.retrieval"):
            raw_chunks = await _do_retrieval(request, trace_id)

        # ── 生成 ─────────────────────────────────────────────────────────────
        with tracer.start_as_current_span("rag.generation"):
            from app.generator import generate_answer
            answer, citations, confidence = await generate_answer(
                query=request.query,
                chunks=raw_chunks,
                trace_id=trace_id,
            )

        # ── 审计日志 ─────────────────────────────────────────────────────────
        await _write_audit_log(trace_id, request, len(raw_chunks), confidence)

        # ── 构建响应 ──────────────────────────────────────────────────────────
        retrieved_chunks = _build_response_chunks(raw_chunks)

        return QueryResponse(
            answer=answer,
            citations=citations,
            evidence_ids=[c.chunk_id for c in retrieved_chunks],
            retrieved_chunks=retrieved_chunks,
            confidence=confidence,
            answer_grounded=confidence >= request.min_score and len(raw_chunks) > 0,
            release_id=settings.release_id,
            trace_id=trace_id,
            session_id=request.session_id,
        )


async def _do_retrieval(request: QueryRequest, trace_id: str):
    """执行混合检索，DB 不可用时降级返回空列表"""
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            from app.retrieval import hybrid_retrieve
            return await hybrid_retrieve(
                conn=conn,
                query=request.query,
                top_k=request.top_k,
                product_line=request.product_line,
                index_release_id=settings.index_release_id,
                rerank=settings.rerank_enabled,
                min_score=0.0,   # 过滤在响应层做
            )
    except Exception as e:
        logger.warning(f"[{trace_id}] Retrieval failed, returning empty: {e}")
        return []


def _build_response_chunks(raw_chunks) -> list[RetrievedChunk]:
    result = []
    for chunk in raw_chunks:
        result.append(RetrievedChunk(
            chunk_id=chunk.chunk_id,
            content=chunk.content,
            score=min(max(chunk.rrf_score * 10, 0.0), 1.0),  # RRF → 0-1 归一化
            rerank_score=chunk.rerank_score,
            evidence_anchor=EvidenceAnchor(
                source_id=chunk.source_id,
                source_url=chunk.source_url,
                page_no=chunk.page_no,
                section_path=chunk.section_path,
                doc_version=chunk.doc_version,
                modality="document",
            ),
        ))
    return result


async def _write_audit_log(trace_id: str, request: QueryRequest, chunk_count: int, confidence: float):
    """写入审计日志（非阻塞，失败不影响主链路）"""
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log
                    (request_id, actor, tool_name, args_hash, result_code,
                     hitl_triggered, release_id, trace_id, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                """,
                trace_id,
                "rag_api",
                "search_knowledge",
                str(hash(request.query))[:16],
                "OK" if chunk_count > 0 else "RETRIEVAL_EMPTY",
                False,
                settings.release_id,
                trace_id,
            )
    except Exception as e:
        logger.warning(f"Audit log write failed (non-fatal): {e}")

"""Hybrid Retrieval — 向量检索 + FTS + Cross-Encoder Rerank

实现混合检索链路：
  1. pgvector ANN 向量检索（语义相似）
  2. PostgreSQL FTS 倒排检索（关键词精确）
  3. RRF (Reciprocal Rank Fusion) 合并两路结果
  4. Cross-Encoder Rerank 精排（可选）
  5. 回填完整 evidence_anchor 字段
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Sequence

logger = logging.getLogger(__name__)


# ── 结果结构 ──────────────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    chunk_id: str
    doc_id: str
    source_id: str
    content: str
    section_path: str
    page_no: int | None
    source_url: str | None
    doc_version: str | None
    section_type: str

    vector_score: float = 0.0
    fts_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float | None = None

    @property
    def final_score(self) -> float:
        return self.rerank_score if self.rerank_score is not None else self.rrf_score


# ── 嵌入查询向量生成 ──────────────────────────────────────────────────────────

class QueryEmbedder:
    """为查询文本生成嵌入向量（复用 pipelines/indexing/embedder 的逻辑）"""

    def __init__(self):
        self._provider = None

    def _get_provider(self):
        if self._provider is None:
            import sys
            sys.path.insert(0, str(os.path.dirname(__file__) + "/../../../"))
            try:
                from pipelines.indexing.embedder import EmbeddingProvider
                self._provider = EmbeddingProvider()
            except ImportError:
                self._provider = _FallbackEmbedder()
        return self._provider

    def embed(self, text: str) -> list[float]:
        return self._get_provider().embed_batch([text])[0]


class _FallbackEmbedder:
    """不可用时返回零向量（测试/骨架场景）"""
    def embed_batch(self, texts):
        return [[0.0] * 1536 for _ in texts]


_query_embedder = QueryEmbedder()


# ── 向量检索 ──────────────────────────────────────────────────────────────────

async def vector_search(
    conn,
    query: str,
    top_k: int,
    product_line: str | None,
    index_release_id: str,
) -> list[RetrievalResult]:
    """ANN 余弦相似度检索（pgvector）"""
    try:
        query_vec = _query_embedder.embed(query)
    except Exception as e:
        logger.warning(f"Embedding failed, skipping vector search: {e}")
        return []

    where_clauses = ["ks.embedding IS NOT NULL", "ks.index_release_id = $2"]
    params: list = [query_vec, index_release_id]

    if product_line and product_line != "any":
        where_clauses.append(f"kd.product_line = ${len(params)+1}")
        params.append(product_line)

    params.append(top_k)

    rows = await conn.fetch(
        f"""
        SELECT
            ks.section_id   AS chunk_id,
            ks.doc_id,
            ks.source_id,
            ks.content,
            ks.section_path,
            ks.section_type,
            ks.page_no,
            kd.source_url,
            kd.doc_version,
            1 - (ks.embedding <=> $1::vector) AS score
        FROM knowledge_section ks
        JOIN knowledge_doc kd ON ks.doc_id = kd.doc_id
        WHERE {" AND ".join(where_clauses)}
        ORDER BY ks.embedding <=> $1::vector
        LIMIT ${len(params)}
        """,
        *params,
    )

    return [
        RetrievalResult(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            source_id=r["source_id"],
            content=r["content"],
            section_path=r["section_path"],
            section_type=r["section_type"],
            page_no=r["page_no"],
            source_url=r["source_url"],
            doc_version=r["doc_version"],
            vector_score=float(r["score"]),
        )
        for r in rows
    ]


# ── FTS 检索 ──────────────────────────────────────────────────────────────────

async def fts_search(
    conn,
    query: str,
    top_k: int,
    product_line: str | None,
    index_release_id: str,
) -> list[RetrievalResult]:
    """PostgreSQL 全文检索（tsvector + tsquery）"""
    where_clauses = [
        "to_tsvector('english', ks.content) @@ plainto_tsquery('english', $1)",
        "ks.index_release_id = $2",
    ]
    params: list = [query, index_release_id]

    if product_line and product_line != "any":
        where_clauses.append(f"kd.product_line = ${len(params)+1}")
        params.append(product_line)

    params.append(top_k)

    try:
        rows = await conn.fetch(
            f"""
            SELECT
                ks.section_id   AS chunk_id,
                ks.doc_id,
                ks.source_id,
                ks.content,
                ks.section_path,
                ks.section_type,
                ks.page_no,
                kd.source_url,
                kd.doc_version,
                ts_rank_cd(to_tsvector('english', ks.content),
                           plainto_tsquery('english', $1)) AS score
            FROM knowledge_section ks
            JOIN knowledge_doc kd ON ks.doc_id = kd.doc_id
            WHERE {" AND ".join(where_clauses)}
            ORDER BY score DESC
            LIMIT ${len(params)}
            """,
            *params,
        )
    except Exception as e:
        logger.warning(f"FTS search failed: {e}")
        return []

    return [
        RetrievalResult(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            source_id=r["source_id"],
            content=r["content"],
            section_path=r["section_path"],
            section_type=r["section_type"],
            page_no=r["page_no"],
            source_url=r["source_url"],
            doc_version=r["doc_version"],
            fts_score=float(r["score"]),
        )
        for r in rows
    ]


# ── RRF 融合 ─────────────────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    vector_results: list[RetrievalResult],
    fts_results: list[RetrievalResult],
    k: int = 60,
) -> list[RetrievalResult]:
    """
    Reciprocal Rank Fusion：合并两路检索结果。
    RRF score = Σ 1/(k + rank_i)
    """
    scores: dict[str, float] = {}
    registry: dict[str, RetrievalResult] = {}

    for rank, result in enumerate(vector_results, 1):
        scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + 1.0 / (k + rank)
        registry[result.chunk_id] = result

    for rank, result in enumerate(fts_results, 1):
        scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + 1.0 / (k + rank)
        if result.chunk_id not in registry:
            registry[result.chunk_id] = result
        else:
            # 合并两路的分数
            existing = registry[result.chunk_id]
            existing.fts_score = result.fts_score

    # 按 RRF 分数排序
    merged = list(registry.values())
    for r in merged:
        r.rrf_score = scores[r.chunk_id]
    merged.sort(key=lambda x: x.rrf_score, reverse=True)
    return merged


# ── Cross-Encoder Rerank ──────────────────────────────────────────────────────

class CrossEncoderReranker:
    """
    Cross-Encoder 精排。
    优先使用 sentence-transformers cross-encoder，
    不可用时跳过（保留 RRF 排序）。
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model = None
        self._model_name = model_name

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self._model_name)
                logger.info(f"Cross-encoder loaded: {self._model_name}")
            except Exception as e:
                logger.warning(f"Cross-encoder not available: {e}. Using RRF scores only.")
                self._model = "unavailable"
        return self._model

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        model = self._get_model()
        if model == "unavailable" or not results:
            return results

        pairs = [[query, r.content] for r in results]
        try:
            scores = model.predict(pairs)
            for result, score in zip(results, scores):
                result.rerank_score = float(score)
            results.sort(key=lambda x: x.rerank_score, reverse=True)
        except Exception as e:
            logger.warning(f"Rerank failed: {e}")

        return results


_reranker = CrossEncoderReranker()


# ── 主检索接口 ────────────────────────────────────────────────────────────────

async def hybrid_retrieve(
    conn,
    query: str,
    top_k: int = 5,
    product_line: str | None = None,
    index_release_id: str = "index-v0.1.0",
    rerank: bool = True,
    min_score: float = 0.0,
) -> list[RetrievalResult]:
    """
    执行完整混合检索：vector + FTS → RRF → rerank → filter
    """
    # 两路并行检索
    vec_results, fts_results = await asyncio.gather(
        vector_search(conn, query, top_k * 2, product_line, index_release_id),
        fts_search(conn, query, top_k * 2, product_line, index_release_id),
    )

    # RRF 融合
    merged = reciprocal_rank_fusion(vec_results, fts_results)

    # Cross-Encoder 精排
    if rerank and merged:
        merged = _reranker.rerank(query, merged[:top_k * 2])

    # 取 top_k + 最低分过滤
    results = merged[:top_k]
    if min_score > 0:
        results = [r for r in results if r.final_score >= min_score]

    return results



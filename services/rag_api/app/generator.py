"""RAG Generator — Claude API 调用 + 证据引用生成

负责：
- 构建 RAG system prompt（含 evidence-first 约束）
- 调用 Claude API 生成答案
- 解析引用，关联 evidence_anchor
- 写入审计日志
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Sequence

from app.config import settings

logger = logging.getLogger(__name__)


# ── Prompt 模板 ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
你是 OmniSupport Copilot，Northstar Systems 的企业支持 AI 助手。

【工作原则】
1. 只回答与 Northstar Systems 产品（Workspace / Edge Gateway / Studio）相关的问题。
2. 回答必须基于以下提供的知识片段（Context），不得凭空捏造。
3. 引用时使用 [来源N] 格式，如 [来源1]、[来源2]。
4. 如果知识片段不足以回答问题，明确说明"当前知识库未覆盖此问题"，不要强行回答。
5. 涉及安全、权限、账单变更时，建议用户联系支持团队或使用工单工具。

【回答格式】
- 简洁、结构化，使用中文
- 引用格式：在相关句子末尾加 [来源N]
- 如有操作步骤，使用编号列表
"""

CONTEXT_TEMPLATE = """\
=== 知识片段 ===
{context_blocks}

=== 用户问题 ===
{query}
"""


def build_context_blocks(chunks) -> str:
    blocks = []
    for i, chunk in enumerate(chunks, 1):
        meta = f"[来源{i}] {chunk.section_path}"
        if chunk.page_no:
            meta += f" (第{chunk.page_no}页)"
        if chunk.source_url:
            meta += f" | {chunk.source_url}"
        blocks.append(f"{meta}\n{chunk.content}")
    return "\n\n---\n\n".join(blocks)


# ── Claude API 调用 ───────────────────────────────────────────────────────────

async def generate_answer(
    query: str,
    chunks,
    trace_id: str,
) -> tuple[str, list[str], float]:
    """
    调用 Claude 生成带引用的回答。

    返回: (answer_text, citations_list, confidence_score)
    """
    if not chunks:
        return (
            "当前知识库未找到与您问题相关的内容，建议创建工单由支持团队处理。",
            [],
            0.0,
        )

    context = build_context_blocks(chunks)
    user_message = CONTEXT_TEMPLATE.format(
        context_blocks=context,
        query=query,
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            metadata={"user_id": trace_id},  # OTel trace 关联
        )

        answer = response.content[0].text

        # 解析答案中的引用标记 [来源N]
        citations = _extract_citations(answer, chunks)

        # 置信度：基于检索得分估算（简化）
        confidence = _estimate_confidence(chunks)

        return answer, citations, confidence

    except anthropic.AuthenticationError:
        logger.error("Anthropic API key invalid")
        return _fallback_answer(query, chunks), [], 0.3
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return _fallback_answer(query, chunks), [], 0.3


def _extract_citations(answer: str, chunks) -> list[str]:
    """从答案文本中提取引用，生成可读的引用列表"""
    import re

    cited_indices: set[int] = set()
    for m in re.finditer(r"\[来源(\d+)\]", answer):
        idx = int(m.group(1)) - 1  # 转为 0-based
        if 0 <= idx < len(chunks):
            cited_indices.add(idx)

    if not cited_indices:
        # 没有引用标记时，列出所有来源
        cited_indices = set(range(len(chunks)))

    citations = []
    for i in sorted(cited_indices):
        chunk = chunks[i]
        cite_parts = []
        if chunk.source_url:
            cite_parts.append(chunk.source_url)
        if chunk.section_path:
            cite_parts.append(chunk.section_path)
        if chunk.page_no:
            cite_parts.append(f"第{chunk.page_no}页")
        citations.append(f"[来源{i+1}] " + " | ".join(cite_parts) if cite_parts else f"[来源{i+1}]")

    return citations


def _estimate_confidence(chunks) -> float:
    """基于检索得分估算置信度（0-1）"""
    if not chunks:
        return 0.0
    top_score = chunks[0].final_score if hasattr(chunks[0], "final_score") else 0.5
    # RRF 分数归一化到 0-1
    if top_score > 1:
        top_score = min(top_score / 0.1, 1.0)  # RRF 最大约 0.1
    return round(min(top_score, 1.0), 3)


def _fallback_answer(query: str, chunks) -> str:
    """Claude API 不可用时的降级答案"""
    if not chunks:
        return "当前知识库未找到相关内容。"
    top = chunks[0]
    return (
        f"（注：AI 服务暂时不可用，以下为最相关知识片段）\n\n"
        f"**{top.section_path}**\n\n{top.content[:500]}..."
    )

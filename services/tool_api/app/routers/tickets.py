"""工单工具端点

Week01 骨架：契约校验框架 + 骨架响应。
Week10 接入真实数据库 CRUD、HITL 触发、审计日志。
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(tags=["ticket-tools"])


# ── 请求/响应模型 ─────────────────────────────────────────────────────────────

class GetTicketRequest(BaseModel):
    ticket_id: str = Field(..., pattern=r"^TKT-[0-9]{8}-[0-9]{6}$")
    include_comments: bool = False


class CreateTicketRequest(BaseModel):
    subject: str = Field(..., max_length=512)
    description: str = Field(..., max_length=8192)
    priority: str = Field(..., pattern=r"^p[1-4]_(critical|high|medium|low)$")
    product_line: str
    category: str
    product_version: Optional[str] = None
    error_codes: list[str] = []
    asset_ids: list[str] = []
    idempotency_key: Optional[str] = None


class AuditLog(BaseModel):
    request_id: str
    actor: str
    tool_name: str
    args_hash: str
    result_code: str
    hitl_triggered: bool
    ts: str


# ── 端点 ──────────────────────────────────────────────────────────────────────

@router.post("/get_ticket_status", summary="查询工单状态")
async def get_ticket_status(req: GetTicketRequest, http_request: Request):
    """
    查询工单状态。

    Week01 骨架：参数校验通过后返回占位数据。
    Week10 替换为真实数据库查询 + 权限校验。
    """
    trace_id = getattr(http_request.state, "request_id", str(uuid.uuid4()))

    # TODO(Week10): 权限校验 (allowed_roles: end_user 只能查自己的工单)
    # TODO(Week10): 真实数据库查询

    return {
        "ticket_id": req.ticket_id,
        "status": "open",                          # stub
        "priority": "p3_medium",                   # stub
        "category": "configuration",               # stub
        "product_line": "northstar_workspace",     # stub
        "assignee_id": None,
        "sla_due_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "resolved_at": None,
        "comments": [] if not req.include_comments else [],
        "trace_id": trace_id,
        "release_id": settings.release_id,
        "_stub": True,  # Week10 删除
    }


@router.post("/create_ticket", summary="创建工单", status_code=201)
async def create_ticket(req: CreateTicketRequest, http_request: Request):
    """
    创建工单。

    Week01 骨架：幂等键检查框架 + HITL 触发判断逻辑 + 占位响应。
    Week10 替换为真实数据库写入。
    """
    trace_id = getattr(http_request.state, "request_id", str(uuid.uuid4()))

    # ── HITL 触发判断（Week10 实际执行时触发 webhook）──────────────────────
    hitl_triggered = _should_trigger_hitl(req.priority, req.category)

    # ── 幂等键检查框架（Week10 查 DB）─────────────────────────────────────
    if req.idempotency_key:
        # TODO(Week10): 查询 DB 是否已存在相同 idempotency_key
        pass

    # ── 生成工单 ID（Week10 从 DB sequence 生成）──────────────────────────
    now = datetime.now(timezone.utc)
    ticket_id = f"TKT-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    # ── 审计日志（Week10 写入 audit_log 表）───────────────────────────────
    audit = AuditLog(
        request_id=trace_id,
        actor="anonymous",    # Week10: 从 JWT/session 提取
        tool_name="create_ticket",
        args_hash=str(hash(req.model_dump_json()))[:16],
        result_code="CREATED",
        hitl_triggered=hitl_triggered,
        ts=now.isoformat(),
    )

    return {
        "ticket_id": ticket_id,
        "status": "open",
        "sla_due_at": None,
        "created_at": now.isoformat(),
        "hitl_triggered": hitl_triggered,
        "trace_id": trace_id,
        "release_id": settings.release_id,
        "_audit": audit.model_dump(),
        "_stub": True,  # Week10 删除
    }


def _should_trigger_hitl(priority: str, category: str) -> bool:
    """根据工具契约中的 hitl_conditions 判断是否触发人工介入"""
    if priority == "p1_critical":
        return True
    if priority == "p2_high" and category == "security":
        return True
    return False

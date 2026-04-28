"""Week05 governed KPI query endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.kpi_query import query_support_kpis

router = APIRouter(tags=["kpis"])


@router.post("/query_support_kpis")
async def query_support_kpis_endpoint(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    payload.setdefault("actor_id", request.headers.get("X-Actor-ID"))
    return await query_support_kpis(payload)

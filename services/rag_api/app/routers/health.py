"""健康检查端点"""

from fastapi import APIRouter
from app.models.rag_models import HealthResponse
from app.config import settings

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="服务健康检查")
async def health_check() -> HealthResponse:
    """
    检查 RAG API 各依赖组件的状态。

    - **status**: ok / degraded / down
    - **checks**: 各组件的健康状态
    """
    checks = {
        "api": "ok",
        "database": await _check_db(),
        "vector_index": "pending",  # Week08 接入
        "llm": "pending",           # Week08 接入
    }

    overall = "ok" if all(v == "ok" for v in checks.values() if v != "pending") else "degraded"

    return HealthResponse(
        status=overall,
        service="rag_api",
        version="0.1.0",
        release_id=settings.release_id,
        checks=checks,
    )


async def _check_db() -> str:
    """简单数据库连接检查"""
    try:
        import asyncpg
        conn = await asyncpg.connect(
            settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
        await conn.execute("SELECT 1")
        await conn.close()
        return "ok"
    except Exception:
        return "down"

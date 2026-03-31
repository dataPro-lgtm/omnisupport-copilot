from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["system"])


@router.get("/health", summary="Tool API 健康检查")
async def health():
    return {
        "status": "ok",
        "service": "tool_api",
        "version": "0.1.0",
        "release_id": settings.release_id,
    }

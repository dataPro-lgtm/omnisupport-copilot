"""管理接口 — Release 信息、索引状态"""

from fastapi import APIRouter
from app.models.rag_models import ReleaseInfoResponse
from app.config import settings

router = APIRouter(tags=["admin"])


@router.get("/release", response_model=ReleaseInfoResponse, summary="当前 Release 版本信息")
async def get_release_info() -> ReleaseInfoResponse:
    return ReleaseInfoResponse(
        release_id=settings.release_id,
        data_release_id=settings.data_release_id,
        index_release_id=settings.index_release_id,
        prompt_release_id=settings.prompt_release_id,
    )

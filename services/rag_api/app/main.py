"""OmniSupport Copilot — RAG API Service

Week01 骨架：提供 health check 和 /query 基础端点。
Week08 起逐步接入真实检索与生成链路。
"""

from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.observability import setup_telemetry
from app.routers import health, query, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动与关闭钩子"""
    setup_telemetry(service_name=settings.otel_service_name)
    yield


app = FastAPI(
    title="OmniSupport Copilot — RAG API",
    description="多模态企业支持知识层检索增强生成服务",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS（开发环境开放，生产环境限制 origin）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── 请求 ID 中间件 ──────────────────────────────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── 全局异常处理 ─────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": str(exc),
            "request_id": getattr(request.state, "request_id", None),
            "release_id": settings.release_id,
        },
    )


# ── 路由注册 ─────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(query.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1/admin")

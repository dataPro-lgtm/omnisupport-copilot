"""OmniSupport Copilot — Tool API Service

工单工具 + HITL + 审计日志服务。
Week01 骨架：提供 health check 和工具调用契约验证框架。
Week10 起接入真实工单 CRUD、HITL 触发、审计日志。
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import health, kpis, tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="OmniSupport Copilot — Tool API",
    description="工单工具链 + HITL + 审计日志服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


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


app.include_router(health.router)
app.include_router(tickets.router, prefix="/api/v1/tools")
app.include_router(kpis.router, prefix="/api/v1/tools")

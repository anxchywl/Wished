from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.integrations.minio.client import get_minio_client

router = APIRouter()


class DependencyHealth(BaseModel):
    """dependency health"""
    status: Literal["ok", "error"]


class HealthResponse(BaseModel):
    """health response"""
    status: Literal["ok", "degraded"]
    database: DependencyHealth
    redis: DependencyHealth
    minio: DependencyHealth


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health(
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> HealthResponse:
    """check service health"""
    database_status: Literal["ok", "error"] = "ok"
    redis_status: Literal["ok", "error"] = "ok"
    minio_status: Literal["ok", "error"] = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    try:
        await redis.ping()
    except Exception:
        redis_status = "error"

    try:
        await run_in_threadpool(get_minio_client().list_buckets)
    except Exception:
        minio_status = "error"

    overall_status: Literal["ok", "degraded"] = (
        "ok"
        if database_status == "ok" and redis_status == "ok" and minio_status == "ok"
        else "degraded"
    )
    if overall_status == "degraded":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        database=DependencyHealth(status=database_status),
        redis=DependencyHealth(status=redis_status),
        minio=DependencyHealth(status=minio_status),
    )

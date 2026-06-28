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

# cap how often unauthenticated /health probes hit the dependencies, so the
# endpoint cannot be used as a cheap resource-amplification vector
_HEALTH_CACHE_KEY = "health:status"
_HEALTH_CACHE_TTL = 10


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

    cached = None
    try:
        cached = await redis.get(_HEALTH_CACHE_KEY)
    except Exception:
        cached = None
    if isinstance(cached, (str, bytes)):
        raw = cached.decode() if isinstance(cached, bytes) else cached
        db_c, redis_c, minio_c = (raw.split(",") + ["error", "error", "error"])[:3]
        database_status = "ok" if db_c == "ok" else "error"
        redis_status = "ok" if redis_c == "ok" else "error"
        minio_status = "ok" if minio_c == "ok" else "error"
    else:
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

        try:
            await redis.setex(
                _HEALTH_CACHE_KEY,
                _HEALTH_CACHE_TTL,
                f"{database_status},{redis_status},{minio_status}",
            )
        except Exception:
            pass

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

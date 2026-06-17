from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis

router = APIRouter()


class DependencyHealth(BaseModel):
    """dependency health"""
    status: Literal["ok", "error"]


class HealthResponse(BaseModel):
    """health response"""
    status: Literal["ok", "degraded"]
    database: DependencyHealth
    redis: DependencyHealth


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health(
    db: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> HealthResponse:
    """check service health"""
    database_status: Literal["ok", "error"] = "ok"
    redis_status: Literal["ok", "error"] = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    try:
        await redis.ping()
    except Exception:
        redis_status = "error"

    overall_status: Literal["ok", "degraded"] = (
        "ok" if database_status == "ok" and redis_status == "ok" else "degraded"
    )

    return HealthResponse(
        status=overall_status,
        database=DependencyHealth(status=database_status),
        redis=DependencyHealth(status=redis_status),
    )

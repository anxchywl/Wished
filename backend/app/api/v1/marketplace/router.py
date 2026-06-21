from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.api.deps.auth import get_current_user
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
from app.db.models import User
from app.modules.marketplace.schemas import ImportClientPayload, ImportResult
from app.modules.marketplace.service import import_product, validate_import_url

router = APIRouter(tags=["marketplace"])


@router.post("/marketplace/import", response_model=ImportResult)
async def post_marketplace_import(
    payload: ImportClientPayload,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportResult:
    """receive client-extracted product data, validate, process image, return result"""
    url, hostname = validate_import_url(payload.original_url)
    return await import_product(payload, url, hostname, current_user.id, settings, redis)

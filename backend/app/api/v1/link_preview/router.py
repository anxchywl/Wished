from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.api.deps.auth import get_current_user
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
from app.db.models import User
from app.modules.link_preview.schemas import LinkPreviewRequest, LinkPreviewResponse
from app.modules.link_preview.service import fetch_link_preview, validate_preview_url

router = APIRouter(tags=["link-preview"])


@router.post("/link-preview", response_model=LinkPreviewResponse)
async def post_link_preview(
    payload: LinkPreviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LinkPreviewResponse:
    """extract product metadata from a URL"""
    url, hostname = validate_preview_url(payload.url)
    return await fetch_link_preview(url, hostname, current_user.id, redis, settings)

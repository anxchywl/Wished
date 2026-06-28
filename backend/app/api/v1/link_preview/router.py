from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.api.deps.auth import get_current_user
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
from app.db.models import User
from app.modules.link_preview.schemas import (
    LinkPreviewRequest,
    LinkPreviewResponse,
    StoreImageRequest,
    StoreImageResponse,
)
from app.modules.link_preview.service import (
    fetch_link_preview,
    store_preview_image,
    validate_preview_url,
)

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


@router.post("/link-preview/store-image", response_model=StoreImageResponse)
async def post_store_preview_image(
    payload: StoreImageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StoreImageResponse:
    """download an external image server-side and return a pending image id for wish creation"""
    from fastapi import HTTPException, status as http_status

    result = await store_preview_image(payload.image_url, current_user.id, redis, settings)
    if result is None:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="could not fetch image"
        )
    pending_id, thumbnail_url = result
    return StoreImageResponse(pending_image_id=pending_id, thumbnail_url=thumbnail_url)

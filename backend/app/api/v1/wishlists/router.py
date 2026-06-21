import base64
import json
import logging
import re
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.core.config import get_settings, Settings
from app.db.models import User
from app.modules.wishlists import (
    create_wishlist,
    delete_wishlist,
    delete_wishlist_cover,
    get_wishlist,
    list_current_user_wishlists,
    reorder_wishlists,
    update_wishlist,
    upload_wishlist_cover,
)
from app.modules.wishlists.schemas import (
    WishlistCreateRequest,
    WishlistListResponse,
    WishlistReorderRequest,
    WishlistResponse,
    WishlistUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wishlists", tags=["wishlists"])


@router.get("", response_model=WishlistListResponse)
async def list_wishlists(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WishlistListResponse:
    """list wishlists"""
    return await list_current_user_wishlists(db, current_user)


@router.get("/{wishlist_id}", response_model=WishlistResponse)
async def get_wishlist_detail(
    wishlist_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WishlistResponse:
    """get wishlist"""
    return await get_wishlist(db, current_user, wishlist_id)


@router.post("", response_model=WishlistResponse, status_code=status.HTTP_201_CREATED)
async def post_wishlist(
    payload: WishlistCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> WishlistResponse:
    """create wishlist"""
    return await create_wishlist(db, current_user, payload, redis=redis)


@router.patch("/reorder", response_model=WishlistListResponse)
async def patch_wishlist_order(
    payload: WishlistReorderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WishlistListResponse:
    """reorder wishlists"""
    return await reorder_wishlists(db, current_user, payload)


@router.patch("/{wishlist_id}", response_model=WishlistResponse)
async def patch_wishlist(
    wishlist_id: UUID,
    payload: WishlistUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WishlistResponse:
    """update wishlist"""
    return await update_wishlist(db, current_user, wishlist_id, payload)


@router.delete("/{wishlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wishlist(
    wishlist_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """delete wishlist"""
    await delete_wishlist(db, current_user, wishlist_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{wishlist_id}/cover", response_model=WishlistResponse)
async def post_wishlist_cover(
    wishlist_id: UUID,
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> WishlistResponse:
    """upload or replace wishlist cover image"""
    return await upload_wishlist_cover(
        db,
        current_user,
        wishlist_id,
        file,
        settings,
        redis,
    )


@router.delete("/{wishlist_id}/cover", response_model=WishlistResponse)
async def remove_wishlist_cover(
    wishlist_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WishlistResponse:
    """remove wishlist cover image"""
    return await delete_wishlist_cover(db, current_user, wishlist_id)


@router.post("/{wishlist_id}/share", status_code=status.HTTP_200_OK)
async def share_wishlist(
    wishlist_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """send a formatted share message to the owner's telegram chat via bot"""
    if not settings.telegram_bot_token or not current_user.username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="share unavailable")

    wishlist = await get_wishlist(db, current_user, wishlist_id)

    start_param = _encode_wishlist_start_param(current_user.username, str(wishlist_id))
    bot_username = settings.telegram_bot_username or ""
    mini_app_url = f"https://t.me/{bot_username}/wished?startapp={start_param}"

    title_escaped = _escape_md(wishlist.title)
    url_escaped = _escape_md_url(mini_app_url)
    text = f"Here, see my wishlist in Wished: [{title_escaped}]({url_escaped})"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={
                "chat_id": current_user.telegram_id,
                "text": text,
                "parse_mode": "MarkdownV2",
            },
        )

    if not resp.is_success:
        logger.error("telegram sendMessage failed: %s", resp.text)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="telegram error")

    return {"ok": True}


def _encode_wishlist_start_param(username: str, wishlist_id: str) -> str:
    payload = json.dumps({"username": username, "wishlistId": wishlist_id}, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
    return f"wl_{b64}"


def _escape_md(text: str) -> str:
    """escape special chars for Telegram MarkdownV2 text/labels"""
    return re.sub(r"([_*\[\]()~`>#+=|{}.!\-])", r"\\\1", text)


def _escape_md_url(url: str) -> str:
    """escape only ) and \\ inside MarkdownV2 link URLs"""
    return url.replace("\\", "\\\\").replace(")", "\\)")

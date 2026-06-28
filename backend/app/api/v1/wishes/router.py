from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
from app.db.models import User
from app.modules.wishes import (
    complete_wish,
    copy_wish,
    create_wish,
    delete_wish,
    list_wishlist_wishes,
    reorder_wishes,
    uncomplete_wish,
    update_wish,
)
from app.modules.wishes.rate_limit import (
    check_wish_complete_limit,
    check_wish_create_limit,
    check_wish_delete_limit,
    check_wish_edit_limit,
)
from app.modules.wishes.schemas import (
    WishCopyRequest,
    WishCreateRequest,
    WishListResponse,
    WishReorderRequest,
    WishResponse,
    WishUpdateRequest,
)

router = APIRouter(tags=["wishes"])


@router.get("/wishlists/{wishlist_id}/wishes", response_model=WishListResponse)
async def list_wishes(
    wishlist_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    share_token: Annotated[str | None, Query()] = None,
) -> WishListResponse:
    """list wishlist wishes"""
    return await list_wishlist_wishes(
        db, current_user, wishlist_id, share_token=share_token, redis=redis
    )


@router.post(
    "/wishlists/{wishlist_id}/wishes",
    response_model=WishResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_wish(
    wishlist_id: UUID,
    payload: WishCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WishResponse:
    """create wish"""
    await check_wish_create_limit(
        redis,
        current_user.id,
        settings.wish_create_per_hour,
        settings.wish_create_per_day,
    )
    return await create_wish(db, current_user, wishlist_id, payload, settings, redis)


@router.patch("/wishlists/{wishlist_id}/wishes/reorder", response_model=WishListResponse)
async def patch_wish_order(
    wishlist_id: UUID,
    payload: WishReorderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> WishListResponse:
    """reorder wishes"""
    return await reorder_wishes(db, current_user, wishlist_id, payload, redis=redis)


@router.patch("/wishes/{wish_id}", response_model=WishResponse)
async def patch_wish(
    wish_id: UUID,
    payload: WishUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WishResponse:
    """update wish"""
    await check_wish_edit_limit(redis, current_user.id, settings.wish_edit_per_hour)
    return await update_wish(db, current_user, wish_id, payload, redis=redis)


@router.post(
    "/wishes/{wish_id}/copy", response_model=WishResponse, status_code=status.HTTP_201_CREATED
)
async def post_wish_copy(
    wish_id: UUID,
    payload: WishCopyRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> WishResponse:
    """copy wish"""
    return await copy_wish(db, current_user, wish_id, payload, redis=redis)


@router.delete("/wishes/{wish_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wish(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """delete wish"""
    await check_wish_delete_limit(redis, current_user.id, settings.wish_delete_per_hour)
    await delete_wish(db, current_user, wish_id, redis=redis)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/wishes/{wish_id}/complete", response_model=WishResponse)
async def post_wish_complete(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> WishResponse:
    """mark wish as fulfilled"""
    await check_wish_complete_limit(redis, current_user.id)
    return await complete_wish(db, current_user, wish_id, redis=redis)


@router.delete("/wishes/{wish_id}/complete", response_model=WishResponse)
async def delete_wish_complete(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> WishResponse:
    """restore fulfilled wish to active"""
    await check_wish_complete_limit(redis, current_user.id)
    return await uncomplete_wish(db, current_user, wish_id, redis=redis)

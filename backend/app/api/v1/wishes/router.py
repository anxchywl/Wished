from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.db.models import User
from app.modules.wishes import (
    copy_wish,
    create_wish,
    delete_wish,
    list_wishlist_wishes,
    reorder_wishes,
    update_wish,
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
) -> WishListResponse:
    """list wishlist wishes"""
    return await list_wishlist_wishes(db, current_user, wishlist_id)


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
) -> WishResponse:
    """create wish"""
    return await create_wish(db, current_user, wishlist_id, payload)


@router.patch("/wishlists/{wishlist_id}/wishes/reorder", response_model=WishListResponse)
async def patch_wish_order(
    wishlist_id: UUID,
    payload: WishReorderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WishListResponse:
    """reorder wishes"""
    return await reorder_wishes(db, current_user, wishlist_id, payload)


@router.patch("/wishes/{wish_id}", response_model=WishResponse)
async def patch_wish(
    wish_id: UUID,
    payload: WishUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WishResponse:
    """update wish"""
    return await update_wish(db, current_user, wish_id, payload)


@router.post("/wishes/{wish_id}/copy", response_model=WishResponse, status_code=status.HTTP_201_CREATED)
async def post_wish_copy(
    wish_id: UUID,
    payload: WishCopyRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WishResponse:
    """copy wish"""
    return await copy_wish(db, current_user, wish_id, payload)


@router.delete("/wishes/{wish_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wish(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """delete wish"""
    await delete_wish(db, current_user, wish_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import User, Wish, Wishlist
from app.integrations.minio import delete_object
from app.modules.wishlists.schemas import (
    WishlistCreateRequest,
    WishlistListResponse,
    WishlistReorderRequest,
    WishlistResponse,
    WishlistUpdateRequest,
)


async def list_current_user_wishlists(db: AsyncSession, current_user: User) -> WishlistListResponse:
    """list current wishlists"""
    result = await db.execute(
        select(Wishlist)
        .where(Wishlist.owner_user_id == current_user.id)
        .order_by(Wishlist.position.asc())
    )
    return WishlistListResponse(items=[_to_response(wishlist) for wishlist in result.scalars().all()])


async def list_user_wishlists(
    db: AsyncSession,
    current_user: User,
    username: str,
    allow_profile_access: bool = False,
) -> WishlistListResponse:
    """list visible user wishlists"""
    user_result = await db.execute(select(User).where(User.username.ilike(username.strip().removeprefix("@"))))
    owner = user_result.scalar_one_or_none()
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if (
        owner.id != current_user.id
        and owner.profile_visibility != "public"
        and not allow_profile_access
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    conditions = [Wishlist.owner_user_id == owner.id]
    if owner.id != current_user.id:
        conditions.append(Wishlist.visibility == "public")

    result = await db.execute(
        select(Wishlist)
        .where(*conditions)
        .order_by(Wishlist.position.asc())
    )
    return WishlistListResponse(items=[_to_response(wishlist) for wishlist in result.scalars().all()])


async def get_wishlist(
    db: AsyncSession,
    current_user: User,
    wishlist_id: UUID,
) -> WishlistResponse:
    """get visible wishlist"""
    wishlist = await get_accessible_wishlist(db, current_user, wishlist_id)
    return _to_response(wishlist)


async def create_wishlist(
    db: AsyncSession,
    current_user: User,
    payload: WishlistCreateRequest,
) -> WishlistResponse:
    """create wishlist"""
    next_position = await _next_wishlist_position(db, current_user)
    wishlist = Wishlist(
        owner_user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        visibility=payload.visibility or current_user.wishlist_visibility,
        position=next_position,
    )
    db.add(wishlist)
    await db.commit()
    await db.refresh(wishlist)
    return _to_response(wishlist)


async def reorder_wishlists(
    db: AsyncSession,
    current_user: User,
    payload: WishlistReorderRequest,
) -> WishlistListResponse:
    """reorder wishlists"""
    result = await db.execute(
        select(Wishlist).where(Wishlist.owner_user_id == current_user.id)
    )
    wishlists = result.scalars().all()
    wishlists_by_id = {wishlist.id: wishlist for wishlist in wishlists}

    if set(payload.wishlist_ids) != set(wishlists_by_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wishlist ids do not match")

    for position, wishlist_id in enumerate(payload.wishlist_ids):
        wishlists_by_id[wishlist_id].position = position

    ordered = [wishlists_by_id[wishlist_id] for wishlist_id in payload.wishlist_ids]
    response = WishlistListResponse(items=[_to_response(wishlist) for wishlist in ordered])
    await db.commit()
    return response


async def update_wishlist(
    db: AsyncSession,
    current_user: User,
    wishlist_id: UUID,
    payload: WishlistUpdateRequest,
) -> WishlistResponse:
    """update wishlist"""
    wishlist = await _get_owned_wishlist(db, current_user, wishlist_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "title" in update_data:
        wishlist.title = payload.title
    if "description" in update_data:
        wishlist.description = payload.description
    if "visibility" in update_data:
        wishlist.visibility = payload.visibility

    await db.commit()
    await db.refresh(wishlist)
    return _to_response(wishlist)


async def delete_wishlist(db: AsyncSession, current_user: User, wishlist_id: UUID) -> None:
    """delete wishlist"""
    wishlist = await _get_owned_wishlist(db, current_user, wishlist_id)
    # find wishes and images
    result = await db.execute(
        select(Wish).options(selectinload(Wish.images)).where(Wish.wishlist_id == wishlist_id)
    )
    wishes = result.scalars().all()
    # collect image coordinates
    images_to_delete = []
    for wish in wishes:
        for img in wish.images:
            images_to_delete.append((img.bucket, img.object_name))
    await db.delete(wishlist)
    await db.commit()
    # clean minio files
    for bucket, object_name in images_to_delete:
        try:
            delete_object(bucket, object_name)
        except Exception:
            pass


async def _get_owned_wishlist(
    db: AsyncSession,
    current_user: User,
    wishlist_id: UUID,
) -> Wishlist:
    """find owned wishlist"""
    result = await db.execute(
        select(Wishlist).where(
            Wishlist.id == wishlist_id,
            Wishlist.owner_user_id == current_user.id,
        )
    )
    wishlist = result.scalar_one_or_none()
    if wishlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    return wishlist


async def _next_wishlist_position(db: AsyncSession, current_user: User) -> int:
    """find next position"""
    result = await db.execute(
        select(func.coalesce(func.min(Wishlist.position), 0)).where(Wishlist.owner_user_id == current_user.id)
    )
    return int(result.scalar_one()) - 1


async def get_accessible_wishlist(
    db: AsyncSession,
    current_user: User,
    wishlist_id: UUID,
) -> Wishlist:
    """find visible wishlist"""
    result = await db.execute(select(Wishlist).where(Wishlist.id == wishlist_id))
    wishlist = result.scalar_one_or_none()
    if wishlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    if wishlist.owner_user_id != current_user.id and wishlist.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    return wishlist


def _to_response(wishlist: Wishlist) -> WishlistResponse:
    """build wishlist response"""
    return WishlistResponse(
        id=wishlist.id,
        owner_user_id=wishlist.owner_user_id,
        title=wishlist.title,
        description=wishlist.description,
        visibility=wishlist.visibility,
        position=wishlist.position,
        created_at=wishlist.created_at,
        updated_at=wishlist.updated_at,
    )

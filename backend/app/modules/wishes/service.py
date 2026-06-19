import logging
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.core.config import get_settings
from app.db.models import User, Wish, WishImage, Wishlist
from app.integrations.minio import copy_object, delete_object, get_presigned_url
from app.modules.media.schemas import WishImageResponse
from app.modules.wishes.schemas import (
    WishCopyRequest,
    WishCreateRequest,
    WishListResponse,
    WishReorderRequest,
    WishResponse,
    WishUpdateRequest,
)
from app.modules.wishlists import get_accessible_wishlist


async def list_wishlist_wishes(
    db: AsyncSession,
    current_user: User,
    wishlist_id: UUID,
) -> WishListResponse:
    """list wishlist wishes"""
    await get_accessible_wishlist(db, current_user, wishlist_id)
    result = await db.execute(
        select(Wish)
        .options(selectinload(Wish.images))
        .where(Wish.wishlist_id == wishlist_id)
        .order_by(Wish.position.asc())
    )
    return WishListResponse(items=[_to_response(wish) for wish in result.scalars().all()])


async def copy_wish(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    payload: WishCopyRequest,
) -> WishResponse:
    """copy wish and duplicate all image variants"""
    source = await _get_accessible_wish(db, current_user, wish_id)
    await _get_owned_wishlist(db, current_user, payload.wishlist_id)
    next_position = await _next_wish_position(db, payload.wishlist_id)

    copied = Wish(
        wishlist_id=payload.wishlist_id,
        title=source.title,
        description=source.description,
        url=source.url,
        priority=source.priority,
        position=next_position,
        price=source.price,
        currency=source.currency,
    )
    db.add(copied)
    await db.flush()

    for image in source.images:
        new_id = uuid4()
        full_obj = f"wishes/{copied.id}/{new_id}"
        thumb_obj = f"wishes/{copied.id}/{new_id}-t"
        medium_obj = f"wishes/{copied.id}/{new_id}-m"

        copy_object(image.bucket, image.object_name, image.bucket, full_obj)
        if image.thumbnail_object_name:
            copy_object(image.bucket, image.thumbnail_object_name, image.bucket, thumb_obj)
        if image.medium_object_name:
            copy_object(image.bucket, image.medium_object_name, image.bucket, medium_obj)

        db.add(
            WishImage(
                id=new_id,
                wish_id=copied.id,
                bucket=image.bucket,
                object_name=full_obj,
                thumbnail_object_name=thumb_obj if image.thumbnail_object_name else None,
                medium_object_name=medium_obj if image.medium_object_name else None,
                file_name=f"{new_id}.webp",
                content_type="image/webp",
                size_bytes=image.size_bytes,
                status="ready",
            )
        )

    await db.commit()
    copied = await _get_owned_wish(db, current_user, copied.id)
    return _to_response(copied)


async def create_wish(
    db: AsyncSession,
    current_user: User,
    wishlist_id: UUID,
    payload: WishCreateRequest,
) -> WishResponse:
    """create wish"""
    await _get_owned_wishlist(db, current_user, wishlist_id)
    next_position = await _next_wish_position(db, wishlist_id)
    wish = Wish(
        wishlist_id=wishlist_id,
        title=payload.title,
        description=payload.description,
        url=payload.url,
        priority=payload.priority,
        position=next_position,
        price=payload.price,
        currency=payload.currency,
    )
    db.add(wish)
    await db.commit()
    wish = await _get_owned_wish(db, current_user, wish.id)
    return _to_response(wish)


async def reorder_wishes(
    db: AsyncSession,
    current_user: User,
    wishlist_id: UUID,
    payload: WishReorderRequest,
) -> WishListResponse:
    """reorder wishes"""
    await _get_owned_wishlist(db, current_user, wishlist_id)
    result = await db.execute(
        select(Wish)
        .options(selectinload(Wish.images))
        .where(Wish.wishlist_id == wishlist_id)
    )
    wishes = result.scalars().all()
    wishes_by_id = {wish.id: wish for wish in wishes}

    if set(payload.wish_ids) != set(wishes_by_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wish ids do not match")

    for position, wish_id in enumerate(payload.wish_ids):
        wishes_by_id[wish_id].position = position

    ordered = [wishes_by_id[wish_id] for wish_id in payload.wish_ids]
    response = WishListResponse(items=[_to_response(wish) for wish in ordered])
    await db.commit()
    return response


async def update_wish(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    payload: WishUpdateRequest,
) -> WishResponse:
    """update wish"""
    wish = await _get_owned_wish(db, current_user, wish_id)
    update_data = payload.model_dump(exclude_unset=True)

    if payload.wishlist_id is not None:
        await _get_owned_wishlist(db, current_user, payload.wishlist_id)
        if payload.wishlist_id != wish.wishlist_id:
            wish.wishlist_id = payload.wishlist_id
            wish.position = await _next_wish_position(db, payload.wishlist_id)
    if "title" in update_data:
        wish.title = payload.title
    if "description" in update_data:
        wish.description = payload.description
    if "url" in update_data:
        wish.url = payload.url
    if "priority" in update_data:
        wish.priority = payload.priority
    if "price" in update_data:
        wish.price = payload.price
        wish.currency = payload.currency

    await db.commit()
    wish = await _get_owned_wish(db, current_user, wish.id)
    return _to_response(wish)


async def delete_wish(db: AsyncSession, current_user: User, wish_id: UUID) -> None:
    """delete wish and all associated image variants from storage"""
    wish = await _get_owned_wish(db, current_user, wish_id)
    objects_to_delete = _collect_image_objects(wish.images)
    await db.delete(wish)
    await db.commit()
    for bucket, obj in objects_to_delete:
        try:
            delete_object(bucket, obj)
        except Exception as exc:
            logger.error("failed to delete minio object %s/%s: %s", bucket, obj, exc)


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


async def _get_owned_wish(db: AsyncSession, current_user: User, wish_id: UUID) -> Wish:
    """find owned wish"""
    result = await db.execute(
        select(Wish)
        .options(selectinload(Wish.images))
        .join(Wishlist, Wishlist.id == Wish.wishlist_id)
        .where(Wish.id == wish_id, Wishlist.owner_user_id == current_user.id)
    )
    wish = result.scalar_one_or_none()
    if wish is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    return wish


async def _next_wish_position(db: AsyncSession, wishlist_id: UUID) -> int:
    """find next position"""
    result = await db.execute(
        select(func.coalesce(func.min(Wish.position), 0)).where(Wish.wishlist_id == wishlist_id)
    )
    return int(result.scalar_one()) - 1


async def _get_accessible_wish(db: AsyncSession, current_user: User, wish_id: UUID) -> Wish:
    """find visible wish"""
    result = await db.execute(
        select(Wish)
        .options(selectinload(Wish.images), selectinload(Wish.wishlist))
        .where(Wish.id == wish_id)
    )
    wish = result.scalar_one_or_none()
    if wish is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    if wish.wishlist.owner_user_id != current_user.id and wish.wishlist.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    return wish


def _collect_image_objects(images: list[WishImage]) -> list[tuple[str, str]]:
    """return (bucket, object_name) for every stored variant across all images"""
    pairs: list[tuple[str, str]] = []
    for img in images:
        pairs.append((img.bucket, img.object_name))
        if img.thumbnail_object_name:
            pairs.append((img.bucket, img.thumbnail_object_name))
        if img.medium_object_name:
            pairs.append((img.bucket, img.medium_object_name))
    return pairs


def _to_response(wish: Wish) -> WishResponse:
    """build wish response with presigned image URLs"""
    return WishResponse(
        id=wish.id,
        wishlist_id=wish.wishlist_id,
        title=wish.title,
        description=wish.description,
        url=wish.url,
        priority=wish.priority,
        position=wish.position,
        price=wish.price,
        currency=wish.currency,
        status=wish.status,
        images=[
            WishImageResponse(
                id=image.id,
                wish_id=image.wish_id,
                url=get_presigned_url(image.bucket, image.object_name),
                thumbnail_url=(
                    get_presigned_url(image.bucket, image.thumbnail_object_name)
                    if image.thumbnail_object_name
                    else None
                ),
                medium_url=(
                    get_presigned_url(image.bucket, image.medium_object_name)
                    if image.medium_object_name
                    else None
                ),
                file_name=image.file_name,
                content_type=image.content_type,
                size_bytes=image.size_bytes,
                status=image.status,
                created_at=image.created_at,
            )
            for image in wish.images
        ],
        created_at=wish.created_at,
        updated_at=wish.updated_at,
    )

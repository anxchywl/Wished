import logging
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.core.config import Settings, get_settings
from app.db.models import Reservation, User, Wish, WishImage, Wishlist
from app.modules.events import publish_event
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
    wishlist = await get_accessible_wishlist(db, current_user, wishlist_id)
    query = (
        select(Wish)
        .options(selectinload(Wish.images))
        .where(Wish.wishlist_id == wishlist_id)
    )
    query = query.order_by(Wish.position.asc())
    result = await db.execute(query)
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
        original_product_url=source.original_product_url,
        source_marketplace=source.source_marketplace,
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
    settings: Settings | None = None,
    redis: Redis | None = None,
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
        original_product_url=payload.original_product_url,
        source_marketplace=payload.source_marketplace,
    )
    db.add(wish)
    await db.flush()

    if payload.pending_marketplace_image_id and redis is not None and settings is not None:
        await _attach_marketplace_image(db, current_user.id, wish.id, payload.pending_marketplace_image_id, settings, redis)

    await db.commit()
    wish = await _get_owned_wish(db, current_user, wish.id)

    if redis is not None:
        await publish_event(redis, "WISH_CREATED", {
            "wish_id": wish.id,
            "wishlist_id": wish.wishlist_id,
            "owner_user_id": current_user.id,
        })

    return _to_response(wish)


async def _attach_marketplace_image(
    db: AsyncSession,
    user_id: UUID,
    wish_id: UUID,
    pending_image_id: UUID,
    settings: Settings,
    redis: Redis,
) -> None:
    """attach a marketplace-imported temp image to a newly created wish"""
    from app.modules.marketplace.service import get_pending_image_meta
    meta = await get_pending_image_meta(redis, user_id, pending_image_id)
    if meta is None:
        # pending image expired or invalid — silently skip
        logger.warning("pending marketplace image not found: user=%s image=%s", user_id, pending_image_id)
        return
    try:
        image = WishImage(
            id=pending_image_id,
            wish_id=wish_id,
            bucket=meta["bucket"],
            object_name=meta["full_key"],
            thumbnail_object_name=meta["thumb_key"],
            medium_object_name=meta["medium_key"],
            file_name=f"{pending_image_id}.webp",
            content_type="image/webp",
            size_bytes=meta.get("size_bytes", 0),
            status="ready",
        )
        db.add(image)
    except (KeyError, TypeError) as exc:
        logger.warning("invalid pending marketplace image metadata: %s", exc)


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
    if "original_product_url" in update_data:
        wish.original_product_url = payload.original_product_url
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


async def complete_wish(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    redis: Redis | None = None,
) -> WishResponse:
    """mark wish as completed and cancel its active reservation"""
    wish = await _get_owned_wish(db, current_user, wish_id)
    if wish.status == "completed":
        return _to_response(wish)
    if wish.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only active wishes can be marked as fulfilled",
        )
    wishlist_id = wish.wishlist_id
    wish.status = "completed"
    result = await db.execute(
        select(Reservation).where(
            Reservation.wish_id == wish_id,
            Reservation.status == "active",
        )
    )
    reservation = result.scalar_one_or_none()
    if reservation is not None:
        reservation.status = "cancelled"
    await db.commit()
    wish = await _get_owned_wish(db, current_user, wish_id)

    if redis is not None:
        await publish_event(redis, "WISH_FULFILLED", {
            "wish_id": wish.id,
            "wishlist_id": wishlist_id,
            "owner_user_id": current_user.id,
        })

    return _to_response(wish)


async def uncomplete_wish(db: AsyncSession, current_user: User, wish_id: UUID) -> WishResponse:
    """restore a completed wish to active"""
    wish = await _get_owned_wish(db, current_user, wish_id)
    if wish.status == "active":
        return _to_response(wish)
    if wish.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed wishes can be restored to active",
        )
    wish.status = "active"
    await db.commit()
    wish = await _get_owned_wish(db, current_user, wish_id)
    return _to_response(wish)


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
        original_product_url=wish.original_product_url,
        source_marketplace=wish.source_marketplace,
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

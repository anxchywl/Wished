import logging
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db.models import Reservation, User, Wish, WishImage, Wishlist
from app.db.models.group_gifts import GroupGift, GroupGiftContribution
from app.modules.events import publish_event
from app.integrations.minio import copy_object, delete_object, get_presigned_url
from app.modules.media.schemas import WishImageResponse
from app.modules.group_gifts.schemas import GroupGiftSummary
from app.modules.wishes.schemas import (
    WishCopyRequest,
    WishCreateRequest,
    WishListResponse,
    WishReorderRequest,
    WishResponse,
    WishUpdateRequest,
)
from app.modules.wishlists import get_accessible_wishlist
from app.modules.cache import (
    cache_delete,
    cache_get_or_fetch,
    wishes_cache_key,
    WISHES_TTL,
)

logger = logging.getLogger(__name__)


async def list_wishlist_wishes(
    db: AsyncSession,
    current_user: User,
    wishlist_id: UUID,
    share_token: str | None = None,
    redis: Redis | None = None,
) -> WishListResponse:
    """list wishlist wishes — owner views are Redis-cached; shared views bypass cache"""
    wishlist = await get_accessible_wishlist(db, current_user, wishlist_id, share_token=share_token, redis=redis)
    is_owner = wishlist.owner_user_id == current_user.id

    async def _fetch() -> WishListResponse:
        query = (
            select(Wish)
            .options(selectinload(Wish.images))
            .where(Wish.wishlist_id == wishlist_id)
            .order_by(Wish.position.asc())
        )
        result = await db.execute(query)
        return WishListResponse(items=[_to_response(wish) for wish in result.scalars().all()])

    # only cache for the authenticated owner; shared-token views skip the cache
    # to avoid leaking stale data across share-token holders
    if redis is not None and not share_token:
        response = await cache_get_or_fetch(
            redis,
            wishes_cache_key(wishlist_id),
            WISHES_TTL,
            WishListResponse,
            _fetch,
        )
    else:
        response = await _fetch()

    # group_gift is user-specific and cannot be cached — enrich after cache lookup
    if response.items:
        response = await _enrich_with_group_gifts(db, response, current_user, is_owner)
    return response


async def copy_wish(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    payload: WishCopyRequest,
    redis: Redis | None = None,
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
        medium_obj = f"wishes/{copied.id}/{new_id}-m"
        thumb_obj = f"wishes/{copied.id}/{new_id}-t"

        src_medium = image.medium_object_name or image.object_name
        copy_object(image.bucket, src_medium, image.bucket, medium_obj)
        if image.thumbnail_object_name:
            copy_object(image.bucket, image.thumbnail_object_name, image.bucket, thumb_obj)

        db.add(
            WishImage(
                id=new_id,
                wish_id=copied.id,
                bucket=image.bucket,
                object_name=medium_obj,
                thumbnail_object_name=thumb_obj if image.thumbnail_object_name else None,
                medium_object_name=medium_obj,
                file_name=f"{new_id}.webp",
                content_type="image/webp",
                size_bytes=image.size_bytes,
                status="ready",
            )
        )

    await db.commit()
    copied = await _get_owned_wish(db, current_user, copied.id)
    if redis is not None:
        await cache_delete(redis, wishes_cache_key(payload.wishlist_id))
        if source.wishlist_id != payload.wishlist_id:
            await cache_delete(redis, wishes_cache_key(source.wishlist_id))
    return _to_response(copied, _build_group_gift_summary(copied.group_gift, current_user, True))


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
        await cache_delete(redis, wishes_cache_key(wishlist_id))
        await publish_event(redis, "WISH_CREATED", {
            "wish_id": wish.id,
            "wishlist_id": wish.wishlist_id,
            "owner_user_id": current_user.id,
        })

    return _to_response(wish, _build_group_gift_summary(wish.group_gift, current_user, True))


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
    redis: Redis | None = None,
) -> WishListResponse:
    """reorder wishes"""
    await _get_owned_wishlist(db, current_user, wishlist_id)
    result = await db.execute(
        select(Wish)
        .options(
            selectinload(Wish.images),
            selectinload(Wish.group_gift).selectinload(GroupGift.contributions),
        )
        .where(Wish.wishlist_id == wishlist_id)
    )
    wishes = result.scalars().all()
    wishes_by_id = {wish.id: wish for wish in wishes}

    if set(payload.wish_ids) != set(wishes_by_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wish ids do not match")

    for position, wish_id in enumerate(payload.wish_ids):
        wishes_by_id[wish_id].position = position

    ordered = [wishes_by_id[wish_id] for wish_id in payload.wish_ids]
    response = WishListResponse(
        items=[
            _to_response(wish, _build_group_gift_summary(wish.group_gift, current_user, True))
            for wish in ordered
        ]
    )
    await db.commit()
    if redis is not None:
        await cache_delete(redis, wishes_cache_key(wishlist_id))
    return response


async def update_wish(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    payload: WishUpdateRequest,
    redis: Redis | None = None,
) -> WishResponse:
    """update wish"""
    wish = await _get_owned_wish(db, current_user, wish_id)
    wishlist_id = wish.wishlist_id
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
    if redis is not None:
        await cache_delete(redis, wishes_cache_key(wish.wishlist_id))
        # if moved to another wishlist, invalidate that wishlist's cache too
        if payload.wishlist_id and payload.wishlist_id != wishlist_id:
            await cache_delete(redis, wishes_cache_key(payload.wishlist_id))
    return _to_response(wish, _build_group_gift_summary(wish.group_gift, current_user, True))


async def delete_wish(db: AsyncSession, current_user: User, wish_id: UUID, redis: Redis | None = None) -> None:
    """delete wish and all associated image variants from storage"""
    wish = await _get_owned_wish(db, current_user, wish_id)
    wishlist_id = wish.wishlist_id
    objects_to_delete = _collect_image_objects(wish.images)
    result = await db.execute(
        select(GroupGift).where(
            GroupGift.wish_id == wish_id,
            GroupGift.status == "active",
        )
    )
    active_gift = result.scalar_one_or_none()
    if active_gift is not None:
        await _cancel_gift_for_deletion(db, active_gift)

    await db.delete(wish)
    await db.commit()
    if redis is not None:
        await cache_delete(redis, wishes_cache_key(wishlist_id))
    for bucket, obj in objects_to_delete:
        try:
            delete_object(bucket, obj)
        except Exception as exc:
            logger.error("failed to delete minio object %s/%s: %s", bucket, obj, exc)


async def _cancel_gift_for_deletion(db: AsyncSession, gift: GroupGift) -> None:
    """cancel an active gift before its wish is deleted"""
    gift.status = "cancelled"
    result = await db.execute(
        select(GroupGiftContribution).where(
            GroupGiftContribution.group_gift_id == gift.id,
            ~GroupGiftContribution.status.in_(["cancelled", "confirmed", "notified"]),
        )
    )
    for contribution in result.scalars().all():
        contribution.status = "cancelled"
    await db.commit()


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
        await cache_delete(redis, wishes_cache_key(wishlist_id))
        await publish_event(redis, "WISH_FULFILLED", {
            "wish_id": wish.id,
            "wishlist_id": wishlist_id,
            "owner_user_id": current_user.id,
        })

    return _to_response(wish, _build_group_gift_summary(wish.group_gift, current_user, True))


async def uncomplete_wish(db: AsyncSession, current_user: User, wish_id: UUID, redis: Redis | None = None) -> WishResponse:
    """restore a completed wish to active"""
    wish = await _get_owned_wish(db, current_user, wish_id)
    if wish.status == "active":
        return _to_response(wish)
    if wish.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed wishes can be restored to active",
        )
    wishlist_id = wish.wishlist_id
    wish.status = "active"
    await db.commit()
    wish = await _get_owned_wish(db, current_user, wish_id)
    if redis is not None:
        await cache_delete(redis, wishes_cache_key(wishlist_id))
    return _to_response(wish, _build_group_gift_summary(wish.group_gift, current_user, True))


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
        .options(
            selectinload(Wish.images),
            selectinload(Wish.group_gift).selectinload(GroupGift.contributions),
        )
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


def _build_group_gift_summary(
    gift: GroupGift | None,
    current_user: User,
    is_owner: bool,
) -> GroupGiftSummary | None:
    """compute caller-specific group gift summary from loaded gift object"""
    if not gift or gift.status != "active":
        return None

    non_cancelled = [c for c in gift.contributions if c.status != "cancelled"]
    is_organizer = gift.organizer_user_id == current_user.id
    is_contributor = any(c.contributor_user_id == current_user.id for c in non_cancelled)

    group_gift_visibility = getattr(current_user, "group_gift_visibility", "hide")
    if is_owner and not is_organizer and not is_contributor and group_gift_visibility == "hide":
        return None

    confirmed_statuses = {"confirmed", "pledged", "notified"}
    collected_amount = sum(
        (c.amount for c in non_cancelled if c.status in confirmed_statuses),
        Decimal("0"),
    )
    total_amount = gift.wish.price if gift.wish else None
    percent_complete = (
        min(100, int(collected_amount / total_amount * 100))
        if total_amount and total_amount > 0
        else 0
    )

    return GroupGiftSummary(
        id=gift.id,
        status=gift.status,
        collection_type=gift.collection_type,
        collected_amount=collected_amount,
        percent_complete=percent_complete,
        contributor_count=len(non_cancelled),
        is_organizer=is_organizer,
        is_contributor=is_contributor,
    )


async def _enrich_with_group_gifts(
    db: AsyncSession,
    response: WishListResponse,
    current_user: User,
    is_owner: bool,
) -> WishListResponse:
    """bulk-load active group gifts for a wish list and attach summaries"""
    wish_ids = [item.id for item in response.items]
    result = await db.execute(
        select(GroupGift)
        .options(
            selectinload(GroupGift.contributions),
            selectinload(GroupGift.wish),
        )
        .where(GroupGift.wish_id.in_(wish_ids), GroupGift.status == "active")
    )
    gifts_by_wish_id = {g.wish_id: g for g in result.scalars().all()}

    enriched = []
    for item in response.items:
        gift = gifts_by_wish_id.get(item.id)
        summary = _build_group_gift_summary(gift, current_user, is_owner)
        enriched.append(item.model_copy(update={"group_gift": summary}))
    return WishListResponse(items=enriched)


def _to_response(wish: Wish, group_gift_summary: GroupGiftSummary | None = None) -> WishResponse:
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
        group_gift=group_gift_summary,
        created_at=wish.created_at,
        updated_at=wish.updated_at,
    )

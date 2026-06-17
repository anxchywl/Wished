from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.db.models import User, Wish, WishImage, Wishlist
from app.integrations.minio import copy_object, delete_object, get_media_object_url
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
    settings = get_settings()
    return WishListResponse(items=[_to_response(wish, settings) for wish in result.scalars().all()])


async def copy_wish(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    payload: WishCopyRequest,
) -> WishResponse:
    """copy wish"""
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
        extension = _extension_for_content_type(image.content_type, image.file_name)
        object_name = f"wishes/{copied.id}/{uuid4()}.{extension}"
        copy_object(image.bucket, image.object_name, image.bucket, object_name)
        db.add(
            WishImage(
                wish_id=copied.id,
                bucket=image.bucket,
                object_name=object_name,
                file_name=image.file_name,
                content_type=image.content_type,
                size_bytes=image.size_bytes,
            )
        )
    await db.commit()
    copied = await _get_owned_wish(db, current_user, copied.id)
    return _to_response(copied, get_settings())


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
    return _to_response(wish, get_settings())


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

    settings = get_settings()
    ordered = [wishes_by_id[wish_id] for wish_id in payload.wish_ids]
    response = WishListResponse(items=[_to_response(wish, settings) for wish in ordered])
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
    return _to_response(wish, get_settings())


async def delete_wish(db: AsyncSession, current_user: User, wish_id: UUID) -> None:
    """delete wish"""
    wish = await _get_owned_wish(db, current_user, wish_id)
    # collect image coordinates
    images_to_delete = [(img.bucket, img.object_name) for img in wish.images]
    await db.delete(wish)
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


def _to_response(wish: Wish, settings: Settings) -> WishResponse:
    """build wish response"""
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
        images=[
            WishImageResponse(
                id=image.id,
                wish_id=image.wish_id,
                url=get_media_object_url(image.bucket, image.object_name),
                file_name=image.file_name,
                content_type=image.content_type,
                size_bytes=image.size_bytes,
                created_at=image.created_at,
            )
            for image in wish.images
        ],
        created_at=wish.created_at,
        updated_at=wish.updated_at,
    )


def _extension_for_content_type(content_type: str, file_name: str) -> str:
    """map image extension"""
    extensions = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    if content_type in extensions:
        return extensions[content_type]
    if "." in file_name:
        return file_name.rsplit(".", 1)[1]
    return "bin"

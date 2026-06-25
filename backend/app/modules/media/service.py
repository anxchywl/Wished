import logging
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import User, Wish, WishImage, Wishlist
from app.integrations.minio import delete_object, get_presigned_url, upload_object
from app.modules.media.processing import process_image
from app.modules.media.rate_limit import check_upload_rate_limit
from app.modules.media.schemas import WishImageListResponse, WishImageResponse
from app.modules.media.validation import validate_image_upload
from app.modules.cache import cache_delete, wishes_cache_key

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


async def list_wish_images(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    settings: Settings,
) -> WishImageListResponse:
    """list wish images — owner only"""
    await _get_owned_wish(db, current_user, wish_id)
    result = await db.execute(
        select(WishImage)
        .where(WishImage.wish_id == wish_id, WishImage.status == "ready")
        .order_by(WishImage.created_at.asc())
    )
    return WishImageListResponse(
        items=[_to_response(image) for image in result.scalars().all()]
    )


async def upload_wish_image(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    file: UploadFile,
    settings: Settings,
    redis: Redis,
) -> WishImageResponse:
    """upload, validate, process, and store a wish image"""
    # rate limiting before any work
    await check_upload_rate_limit(
        redis,
        current_user.id,
        settings.upload_rate_per_minute,
        settings.upload_rate_per_hour,
    )

    await _get_owned_wish(db, current_user, wish_id)

    # image count limit
    count_result = await db.execute(
        select(WishImage)
        .where(WishImage.wish_id == wish_id, WishImage.status == "ready")
    )
    existing = count_result.scalars().all()
    if len(existing) >= settings.max_images_per_wish:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"maximum {settings.max_images_per_wish} images per wish",
        )

    # read upload — enforce size limit
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="file exceeds 5 MB limit",
        )

    # three-layer validation: extension + declared MIME + magic bytes
    validate_image_upload(
        filename=file.filename or "",
        declared_content_type=file.content_type or "",
        content=content,
    )

    # server-side processing: strip EXIF, convert to WebP, generate variants
    try:
        thumbnail_bytes, medium_bytes = process_image(content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # UUID-only object names — never expose original filename or extension
    image_id = uuid4()
    bucket = settings.minio_media_bucket
    medium_name = f"wishes/{wish_id}/{image_id}-m"
    thumb_name = f"wishes/{wish_id}/{image_id}-t"

    upload_object(bucket, medium_name, medium_bytes, "image/webp")
    upload_object(bucket, thumb_name, thumbnail_bytes, "image/webp")

    image = WishImage(
        id=image_id,
        wish_id=wish_id,
        bucket=bucket,
        object_name=medium_name,
        thumbnail_object_name=thumb_name,
        medium_object_name=medium_name,
        file_name=f"{image_id}.webp",
        content_type="image/webp",
        size_bytes=len(medium_bytes),
        status="ready",
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    # wish list responses embed images — invalidate after upload
    wish = await _get_owned_wish(db, current_user, wish_id)
    await cache_delete(redis, wishes_cache_key(wish.wishlist_id))

    return _to_response(image)


async def delete_wish_image(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    image_id: UUID,
    redis: Redis | None = None,
) -> None:
    """delete wish image and all stored variants"""
    wish = await _get_owned_wish(db, current_user, wish_id)
    result = await db.execute(
        select(WishImage).where(WishImage.id == image_id, WishImage.wish_id == wish_id)
    )
    image = result.scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image not found")

    for obj in _image_object_names(image):
        try:
            delete_object(image.bucket, obj)
        except Exception as exc:
            logger.error("failed to delete minio object %s/%s: %s", image.bucket, obj, exc)
    await db.delete(image)
    await db.commit()
    if redis is not None:
        await cache_delete(redis, wishes_cache_key(wish.wishlist_id))


async def _get_owned_wish(db: AsyncSession, current_user: User, wish_id: UUID) -> Wish:
    """find wish owned by current user"""
    result = await db.execute(
        select(Wish)
        .join(Wishlist, Wishlist.id == Wish.wishlist_id)
        .where(Wish.id == wish_id, Wishlist.owner_user_id == current_user.id)
    )
    wish = result.scalar_one_or_none()
    if wish is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="wish not found")
    return wish


def _image_object_names(image: WishImage) -> list[str]:
    """collect all object names for an image record"""
    names = [image.object_name]
    if image.thumbnail_object_name:
        names.append(image.thumbnail_object_name)
    if image.medium_object_name:
        names.append(image.medium_object_name)
    return names


def _to_response(image: WishImage) -> WishImageResponse:
    """build image response with presigned URLs"""
    return WishImageResponse(
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

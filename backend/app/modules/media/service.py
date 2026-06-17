from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import User, Wish, WishImage, Wishlist
from app.integrations.minio import delete_object, get_media_object_url, upload_object
from app.modules.media.schemas import WishImageListResponse, WishImageResponse

ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024


async def list_wish_images(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    settings: Settings,
) -> WishImageListResponse:
    """list wish images"""
    await _get_owned_wish(db, current_user, wish_id)
    result = await db.execute(
        select(WishImage).where(WishImage.wish_id == wish_id).order_by(WishImage.created_at.asc())
    )
    return WishImageListResponse(
        items=[_to_response(image, settings) for image in result.scalars().all()]
    )


async def upload_wish_image(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    file: UploadFile,
    settings: Settings,
) -> WishImageResponse:
    """upload wish image"""
    await _get_owned_wish(db, current_user, wish_id)
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported image type")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image is empty")
    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is too large")

    # delete existing images
    existing_images_result = await db.execute(
        select(WishImage).where(WishImage.wish_id == wish_id)
    )
    existing_images = existing_images_result.scalars().all()
    for old_img in existing_images:
        try:
            delete_object(old_img.bucket, old_img.object_name)
        except Exception:
            pass
        await db.delete(old_img)

    extension = _extension_for_content_type(content_type)
    object_name = f"wishes/{wish_id}/{uuid4()}.{extension}"
    bucket = settings.minio_media_bucket
    upload_object(bucket, object_name, content, content_type)

    image = WishImage(
        wish_id=wish_id,
        bucket=bucket,
        object_name=object_name,
        file_name=file.filename or f"image.{extension}",
        content_type=content_type,
        size_bytes=len(content),
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return _to_response(image, settings)



async def delete_wish_image(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    image_id: UUID,
) -> None:
    """delete wish image"""
    await _get_owned_wish(db, current_user, wish_id)
    result = await db.execute(
        select(WishImage).where(WishImage.id == image_id, WishImage.wish_id == wish_id)
    )
    image = result.scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    delete_object(image.bucket, image.object_name)
    await db.delete(image)
    await db.commit()


async def _get_owned_wish(db: AsyncSession, current_user: User, wish_id: UUID) -> Wish:
    """find owned wish"""
    result = await db.execute(
        select(Wish)
        .join(Wishlist, Wishlist.id == Wish.wishlist_id)
        .where(Wish.id == wish_id, Wishlist.owner_user_id == current_user.id)
    )
    wish = result.scalar_one_or_none()
    if wish is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    return wish


def _to_response(image: WishImage, settings: Settings) -> WishImageResponse:
    """build image response"""
    return WishImageResponse(
        id=image.id,
        wish_id=image.wish_id,
        url=get_media_object_url(image.bucket, image.object_name),
        file_name=image.file_name,
        content_type=image.content_type,
        size_bytes=image.size_bytes,
        created_at=image.created_at,
    )


def _extension_for_content_type(content_type: str) -> str:
    """map content extension"""
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }[content_type]

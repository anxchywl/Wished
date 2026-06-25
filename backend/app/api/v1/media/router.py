from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
from app.db.models import User, Wish, WishImage, Wishlist
from app.integrations.minio import get_presigned_url
from app.modules.media import delete_wish_image, list_wish_images, upload_wish_image
from app.modules.media.schemas import WishImageListResponse, WishImageResponse

router = APIRouter(tags=["media"])


@router.get("/wishes/{wish_id}/images", response_model=WishImageListResponse)
async def get_wish_images(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WishImageListResponse:
    """list wish images"""
    return await list_wish_images(db, current_user, wish_id, settings)


@router.post(
    "/wishes/{wish_id}/images",
    response_model=WishImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_wish_image(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[Redis, Depends(get_redis)],
    file: UploadFile = File(...),
) -> WishImageResponse:
    """upload wish image — validates, processes, and stores server-side"""
    return await upload_wish_image(db, current_user, wish_id, file, settings, redis)


@router.delete("/wishes/{wish_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wish_image(
    wish_id: UUID,
    image_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> Response:
    """delete wish image and all stored variants"""
    await delete_wish_image(db, current_user, wish_id, image_id, redis=redis)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/media/{image_id}", response_class=RedirectResponse)
async def serve_media(
    image_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RedirectResponse:
    """validate access and redirect to presigned URL for the full-size image"""
    image = await _get_accessible_image(db, current_user, image_id)
    return RedirectResponse(
        url=get_presigned_url(image.bucket, image.object_name),
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/media/{image_id}/thumbnail", response_class=RedirectResponse)
async def serve_media_thumbnail(
    image_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RedirectResponse:
    """validate access and redirect to presigned URL for the thumbnail"""
    image = await _get_accessible_image(db, current_user, image_id)
    obj = image.thumbnail_object_name or image.object_name
    return RedirectResponse(
        url=get_presigned_url(image.bucket, obj),
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/media/{image_id}/medium", response_class=RedirectResponse)
async def serve_media_medium(
    image_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RedirectResponse:
    """validate access and redirect to presigned URL for the medium variant"""
    image = await _get_accessible_image(db, current_user, image_id)
    obj = image.medium_object_name or image.object_name
    return RedirectResponse(
        url=get_presigned_url(image.bucket, obj),
        status_code=status.HTTP_302_FOUND,
    )


async def _get_accessible_image(
    db: AsyncSession,
    current_user: User,
    image_id: UUID,
) -> WishImage:
    """load a ready image the current user is allowed to view"""
    result = await db.execute(
        select(WishImage, Wishlist)
        .join(Wish, Wish.id == WishImage.wish_id)
        .join(Wishlist, Wishlist.id == Wish.wishlist_id)
        .where(WishImage.id == image_id, WishImage.status == "ready")
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image not found")

    image, wishlist = row
    if wishlist.owner_user_id != current_user.id and wishlist.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image not found")

    return image

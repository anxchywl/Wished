from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.core.config import Settings, get_settings
from app.db.models import User
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
    file: UploadFile = File(...),
) -> WishImageResponse:
    """upload wish image"""
    return await upload_wish_image(db, current_user, wish_id, file, settings)


@router.delete("/wishes/{wish_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wish_image(
    wish_id: UUID,
    image_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """delete wish image"""
    await delete_wish_image(db, current_user, wish_id, image_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

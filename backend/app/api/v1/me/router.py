from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.db.models import User
from app.modules.profiles import build_profile_response, update_current_profile
from app.modules.profiles.schemas import ProfileResponse, ProfileUpdateRequest

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=ProfileResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProfileResponse:
    """get current profile"""
    return build_profile_response(current_user)


@router.patch("", response_model=ProfileResponse)
async def patch_me(
    payload: ProfileUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileResponse:
    """update current profile"""
    return await update_current_profile(db, current_user, payload)

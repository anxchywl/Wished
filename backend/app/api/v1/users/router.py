"""users api routes"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.db.models import User
from app.modules.users import build_user_profile_response, get_user_by_username, search_users
from app.modules.users.schemas import UserProfileResponse, UserSearchResponse
from app.modules.wishlists import list_user_wishlists
from app.modules.wishlists.schemas import WishlistListResponse

router = APIRouter(tags=["users"])


@router.get("/users/search", response_model=list[UserSearchResponse])
async def get_users_search(
    q: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[UserSearchResponse]:
    """search users by query"""
    return await search_users(db, q, current_user)


@router.get("/users/{username}", response_model=UserProfileResponse)
async def get_user_profile(
    username: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserProfileResponse:
    """get user profile"""
    clean_username = username.removeprefix("@")
    user = (
        current_user
        if current_user.username and current_user.username.lower() == clean_username.lower()
        else await get_user_by_username(db, clean_username)
    )
    return build_user_profile_response(user, current_user)


@router.get("/users/{username}/wishlists", response_model=WishlistListResponse)
async def get_user_wishlists(
    username: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WishlistListResponse:
    """list user wishlists"""
    return await list_user_wishlists(db, current_user, username)

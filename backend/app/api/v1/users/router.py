"""users api routes"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.db.models import User
from app.modules.users import (
    build_user_profile_response,
    follow_user,
    follow_user_by_id,
    get_user_by_id,
    get_user_by_username,
    is_following_user,
    list_followed_users,
    unfollow_user,
    unfollow_user_by_id,
)
from app.modules.users.discovery import validate_discovery_token
from app.modules.users.rate_limit import check_follow_limit, check_unfollow_limit
from app.modules.users.schemas import FollowedUserListResponse, UserProfileResponse
from app.core.config import Settings, get_settings
from app.modules.wishlists import list_user_wishlists, list_user_wishlists_by_id
from app.modules.wishlists.schemas import WishlistListResponse

router = APIRouter(tags=["users"])


@router.get("/users/following", response_model=FollowedUserListResponse)
async def get_following(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FollowedUserListResponse:
    """list followed users"""
    return await list_followed_users(db, current_user)


@router.get("/users/id/{user_id}", response_model=UserProfileResponse)
async def get_user_profile_by_id(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    profile_token: str | None = None,
) -> UserProfileResponse:
    """get user profile by internal UUID"""
    user = (
        current_user
        if current_user.id == user_id
        else await get_user_by_id(db, user_id)
    )
    has_discovery_access = await validate_discovery_token(
        redis,
        profile_token,
        current_user.telegram_id,
        user.telegram_id,
        db=db,
    )
    is_following = await is_following_user(db, current_user, user)
    if (
        user.id != current_user.id
        and user.profile_visibility != "public"
        and not has_discovery_access
        and not is_following
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return build_user_profile_response(user, current_user, is_following=is_following)


@router.post("/users/id/{user_id}/follow", response_model=UserProfileResponse)
async def post_user_follow_by_id(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
    profile_token: str | None = None,
) -> UserProfileResponse:
    """follow user by internal UUID"""
    await check_follow_limit(redis, current_user.id, settings.follow_per_hour)
    target = await get_user_by_id(db, user_id)
    has_discovery_access = await validate_discovery_token(
        redis, profile_token, current_user.telegram_id, target.telegram_id, db=db,
    )
    return await follow_user_by_id(db, current_user, user_id, has_discovery_access=has_discovery_access, redis=redis)


@router.delete("/users/id/{user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_follow_by_id(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """unfollow user by internal UUID"""
    await check_unfollow_limit(redis, current_user.id, settings.unfollow_per_hour)
    await unfollow_user_by_id(db, current_user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/id/{user_id}/wishlists", response_model=WishlistListResponse)
async def get_user_wishlists_by_id(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    profile_token: str | None = None,
) -> WishlistListResponse:
    """list user wishlists by internal UUID"""
    target_user = await get_user_by_id(db, user_id)
    has_discovery_access = await validate_discovery_token(
        redis,
        profile_token,
        current_user.telegram_id,
        target_user.telegram_id,
        db=db,
    )
    is_following = await is_following_user(db, current_user, target_user)
    return await list_user_wishlists_by_id(
        db,
        current_user,
        user_id,
        allow_profile_access=has_discovery_access or is_following,
    )


@router.get("/users/{username}", response_model=UserProfileResponse)
async def get_user_profile(
    username: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    profile_token: str | None = None,
) -> UserProfileResponse:
    """get user profile"""
    clean_username = username.removeprefix("@")
    user = (
        current_user
        if current_user.username and current_user.username.lower() == clean_username.lower()
        else await get_user_by_username(db, clean_username)
    )
    has_discovery_access = await validate_discovery_token(
        redis,
        profile_token,
        current_user.telegram_id,
        user.telegram_id,
        db=db,
    )
    is_following = await is_following_user(db, current_user, user)
    if (
        user.id != current_user.id
        and user.profile_visibility != "public"
        and not has_discovery_access
        and not is_following
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return build_user_profile_response(user, current_user, is_following=is_following)


@router.post("/users/{username}/follow", response_model=UserProfileResponse)
async def post_user_follow(
    username: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
    profile_token: str | None = None,
) -> UserProfileResponse:
    """follow user"""
    await check_follow_limit(redis, current_user.id, settings.follow_per_hour)
    target = await get_user_by_username(db, username.removeprefix("@"))
    has_discovery_access = await validate_discovery_token(
        redis, profile_token, current_user.telegram_id, target.telegram_id, db=db,
    )
    return await follow_user(db, current_user, username, has_discovery_access=has_discovery_access, redis=redis)


@router.delete("/users/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_follow(
    username: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """unfollow user"""
    await check_unfollow_limit(redis, current_user.id, settings.unfollow_per_hour)
    await unfollow_user(db, current_user, username)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{username}/wishlists", response_model=WishlistListResponse)
async def get_user_wishlists(
    username: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    profile_token: str | None = None,
) -> WishlistListResponse:
    """list user wishlists"""
    target_user = await get_user_by_username(db, username)
    has_discovery_access = await validate_discovery_token(
        redis,
        profile_token,
        current_user.telegram_id,
        target_user.telegram_id,
        db=db,
    )
    is_following = await is_following_user(db, current_user, target_user)
    return await list_user_wishlists(
        db,
        current_user,
        username,
        allow_profile_access=has_discovery_access or is_following,
    )

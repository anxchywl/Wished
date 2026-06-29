# user service
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Follow, User
from app.modules.events import publish_event
from app.modules.users.schemas import (
    FollowedUserListResponse,
    FollowedUserReorderRequest,
    FollowedUserResponse,
    UserProfileResponse,
)
from app.modules.cache import cache_delete, cache_get_or_fetch, following_cache_key, FOLLOWING_TTL


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User:
    """find user by id; blocked users are treated as not found"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.is_blocked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> User:
    """find user by username; blocked users are treated as not found"""
    normalized_username = _normalize_username(username)
    result = await db.execute(select(User).where(User.username.ilike(normalized_username)))
    user = result.scalar_one_or_none()
    if user is None or user.is_blocked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _normalize_username(username: str) -> str:
    """normalize username"""
    return username.strip().removeprefix("@")


async def list_followed_users(
    db: AsyncSession,
    current_user: User,
    redis: Redis | None = None,
) -> FollowedUserListResponse:
    """list followed users — Redis-cached per user"""
    if redis is not None:
        return await cache_get_or_fetch(
            redis,
            following_cache_key(current_user.id),
            FOLLOWING_TTL,
            FollowedUserListResponse,
            lambda: _fetch_followed_users(db, current_user),
        )
    return await _fetch_followed_users(db, current_user)


async def _fetch_followed_users(db: AsyncSession, current_user: User) -> FollowedUserListResponse:
    result = await db.execute(
        select(Follow, User)
        .join(User, User.id == Follow.followed_user_id)
        .where(Follow.follower_user_id == current_user.id)
        .order_by(Follow.position.asc())
    )
    return FollowedUserListResponse(
        items=[
            FollowedUserResponse(
                **build_user_profile_response(user, current_user, is_following=True).model_dump(),
                followed_at=follow.created_at,
                position=follow.position,
            )
            for follow, user in result.all()
        ]
    )


async def follow_user(
    db: AsyncSession,
    current_user: User,
    username: str,
    has_discovery_access: bool = False,
    redis: Redis | None = None,
) -> UserProfileResponse:
    """follow user"""
    target = await get_user_by_username(db, username)
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself"
        )
    if target.profile_visibility != "public" and not has_discovery_access:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    already_following = False
    next_position = await _next_follow_position(db, current_user.id)
    db.add(
        Follow(
            follower_user_id=current_user.id,
            followed_user_id=target.id,
            position=next_position,
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        already_following = True

    if not already_following and redis is not None:
        await cache_delete(redis, following_cache_key(current_user.id))
        await publish_event(
            redis,
            "FOLLOWED",
            {
                "follower_user_id": current_user.id,
                "followed_user_id": target.id,
            },
        )

    return build_user_profile_response(target, current_user, is_following=True)


async def unfollow_user(
    db: AsyncSession, current_user: User, username: str, redis: Redis | None = None
) -> UserProfileResponse:
    """unfollow user"""
    target = await get_user_by_username(db, username)
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot unfollow yourself"
        )

    await db.execute(
        delete(Follow).where(
            Follow.follower_user_id == current_user.id,
            Follow.followed_user_id == target.id,
        )
    )
    await db.commit()
    if redis is not None:
        await cache_delete(redis, following_cache_key(current_user.id))
    return build_user_profile_response(target, current_user, is_following=False)


async def follow_user_by_id(
    db: AsyncSession,
    current_user: User,
    target_id: UUID,
    has_discovery_access: bool = False,
    redis: Redis | None = None,
) -> UserProfileResponse:
    """follow user by internal UUID"""
    target = await get_user_by_id(db, target_id)
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself"
        )
    if target.profile_visibility != "public" and not has_discovery_access:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    already_following = False
    next_position = await _next_follow_position(db, current_user.id)
    db.add(
        Follow(
            follower_user_id=current_user.id,
            followed_user_id=target.id,
            position=next_position,
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        already_following = True

    if not already_following and redis is not None:
        await cache_delete(redis, following_cache_key(current_user.id))
        await publish_event(
            redis,
            "FOLLOWED",
            {
                "follower_user_id": current_user.id,
                "followed_user_id": target.id,
            },
        )

    return build_user_profile_response(target, current_user, is_following=True)


async def unfollow_user_by_id(
    db: AsyncSession, current_user: User, target_id: UUID, redis: Redis | None = None
) -> UserProfileResponse:
    """unfollow user by internal UUID"""
    target = await get_user_by_id(db, target_id)
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot unfollow yourself"
        )

    await db.execute(
        delete(Follow).where(
            Follow.follower_user_id == current_user.id,
            Follow.followed_user_id == target.id,
        )
    )
    await db.commit()
    if redis is not None:
        await cache_delete(redis, following_cache_key(current_user.id))
    return build_user_profile_response(target, current_user, is_following=False)


async def is_following_user(db: AsyncSession, current_user: User, user: User) -> bool:
    """check follow state"""
    if current_user.id == user.id:
        return False
    result = await db.execute(
        select(Follow.id).where(
            Follow.follower_user_id == current_user.id,
            Follow.followed_user_id == user.id,
        )
    )
    return result.scalar_one_or_none() is not None


async def reorder_followed_users(
    db: AsyncSession,
    current_user: User,
    payload: FollowedUserReorderRequest,
    redis: Redis | None = None,
) -> FollowedUserListResponse:
    """reorder followed users"""
    result = await db.execute(
        select(Follow)
        .join(User, User.id == Follow.followed_user_id)
        .where(Follow.follower_user_id == current_user.id)
    )
    follows = result.scalars().all()
    follows_by_user_id = {follow.followed_user_id: follow for follow in follows}

    if set(payload.user_ids) != set(follows_by_user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User ids do not match")

    for position, user_id in enumerate(payload.user_ids):
        follows_by_user_id[user_id].position = position

    await db.commit()
    if redis is not None:
        await cache_delete(redis, following_cache_key(current_user.id))
    return await _fetch_followed_users(db, current_user)


def build_user_profile_response(
    user: User,
    current_user: User | None = None,
    is_following: bool = False,
) -> UserProfileResponse:
    """build user profile response — birthday is shown to anyone who can view the profile"""
    is_owner = current_user is not None and current_user.id == user.id
    return UserProfileResponse(
        user_id=str(user.id),
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        photo_url=user.photo_url,
        birthday=user.birthday,
        is_self=is_owner,
        is_following=False if is_owner else is_following,
    )


async def _next_follow_position(db: AsyncSession, follower_user_id: UUID) -> int:
    """find next follow position"""
    result = await db.execute(
        select(func.coalesce(func.min(Follow.position), 0)).where(
            Follow.follower_user_id == follower_user_id
        )
    )
    return result.scalar_one() - 1

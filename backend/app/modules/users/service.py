# user service
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Follow, User
from app.modules.users.schemas import FollowedUserListResponse, FollowedUserResponse, UserProfileResponse


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """find user by id"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User:
    """find user by username"""
    normalized_username = _normalize_username(username)
    result = await db.execute(select(User).where(User.username.ilike(normalized_username)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _normalize_username(username: str) -> str:
    """normalize username"""
    return username.strip().removeprefix("@")


async def list_followed_users(db: AsyncSession, current_user: User) -> FollowedUserListResponse:
    """list followed users"""
    result = await db.execute(
        select(Follow, User)
        .join(User, User.id == Follow.followed_user_id)
        .where(Follow.follower_user_id == current_user.id)
        .order_by(Follow.created_at.desc())
    )
    return FollowedUserListResponse(
        items=[
            FollowedUserResponse(
                **build_user_profile_response(user, current_user, is_following=True).model_dump(),
                followed_at=follow.created_at,
            )
            for follow, user in result.all()
        ]
    )


async def follow_user(
    db: AsyncSession,
    current_user: User,
    username: str,
    has_discovery_access: bool = False,
) -> UserProfileResponse:
    """follow user"""
    target = await get_user_by_username(db, username)
    if target.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself")
    if target.profile_visibility != "public" and not has_discovery_access:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.add(Follow(follower_user_id=current_user.id, followed_user_id=target.id))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
    return build_user_profile_response(target, current_user, is_following=True)


async def unfollow_user(db: AsyncSession, current_user: User, username: str) -> UserProfileResponse:
    """unfollow user"""
    target = await get_user_by_username(db, username)
    if target.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot unfollow yourself")

    await db.execute(
        delete(Follow).where(
            Follow.follower_user_id == current_user.id,
            Follow.followed_user_id == target.id,
        )
    )
    await db.commit()
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


def build_user_profile_response(
    user: User,
    current_user: User | None = None,
    is_following: bool = False,
) -> UserProfileResponse:
    """build user profile response"""
    is_owner = current_user is not None and current_user.id == user.id
    return UserProfileResponse(
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        photo_url=user.photo_url,
        birthday=user.birthday if is_owner or user.birthday_visibility == "public" else None,
        is_self=is_owner,
        is_following=False if is_owner else is_following,
    )

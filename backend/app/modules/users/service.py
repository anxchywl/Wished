# user service
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.modules.users.schemas import UserProfileResponse, UserSearchResponse


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


async def search_users(db: AsyncSession, query: str, current_user: User) -> list[UserSearchResponse]:
    """search users by username"""
    query = _normalize_username(query)
    if not query:
        return []

    result = await db.execute(
        select(User)
        .where(User.username.ilike(f"%{query}%"))
        .where(User.id != current_user.id)
        .limit(20)
    )
    return [_to_search_response(user) for user in result.scalars().all()]


def _normalize_username(username: str) -> str:
    """normalize username"""
    return username.strip().removeprefix("@")


def _to_search_response(user: User) -> UserSearchResponse:
    """build search response"""
    return UserSearchResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        photo_url=user.photo_url,
        birthday=user.birthday,
    )


def build_user_profile_response(user: User, current_user: User | None = None) -> UserProfileResponse:
    """build user profile response"""
    return UserProfileResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        photo_url=user.photo_url,
        birthday=user.birthday,
    )

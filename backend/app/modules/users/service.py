# user service
import re
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import Follow, ProfileUsernameAlias, User
from app.modules.events import publish_event
from app.modules.users.schemas import (
    FollowedUserListResponse,
    FollowedUserReorderRequest,
    FollowedUserResponse,
    UserProfileResponse,
)
from app.modules.cache import cache_delete, cache_get_or_fetch, following_cache_key, FOLLOWING_TTL


PUBLIC_USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,32}$")
RESERVED_PUBLIC_USERNAMES = {
    "admin",
    "api",
    "settings",
    "login",
    "help",
    "support",
    "about",
    "users",
    "me",
    "wishlists",
    "wishes",
    "auth",
    "static",
    "assets",
}


async def get_user_by_id(db: AsyncSession, user_id: UUID, allow_blocked: bool = False) -> User:
    """find user by id; blocked users are treated as not found unless allow_blocked is True"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or (user.is_blocked and not allow_blocked):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def get_user_by_username(
    db: AsyncSession, username: str, allow_blocked: bool = False
) -> User:
    """find user by username; blocked users are treated as not found unless allow_blocked is True"""
    normalized_username = _normalize_username(username)
    result = await db.execute(select(User).where(User.username.ilike(normalized_username)))
    user = result.scalar_one_or_none()
    if user is None or (user.is_blocked and not allow_blocked):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def get_user_by_public_username(
    db: AsyncSession, public_username: str, allow_blocked: bool = False
) -> User:
    """find user by current public username or historic alias"""
    normalized_username = normalize_public_username(public_username)
    if not is_valid_public_username(normalized_username):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(select(User).where(User.public_username == normalized_username))
    user = result.scalar_one_or_none()
    if user is None:
        result = await db.execute(
            select(User)
            .join(ProfileUsernameAlias, ProfileUsernameAlias.user_id == User.id)
            .where(ProfileUsernameAlias.username == normalized_username)
        )
        user = result.scalar_one_or_none()
    if user is None or (user.is_blocked and not allow_blocked):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _normalize_username(username: str) -> str:
    """normalize username"""
    return username.strip().removeprefix("@")


def normalize_public_username(username: str | None) -> str:
    """normalize public username"""
    return (username or "").strip().removeprefix("@").lower()


def is_valid_public_username(username: str | None) -> bool:
    """validate public username format and reserved names"""
    normalized_username = normalize_public_username(username)
    return (
        bool(PUBLIC_USERNAME_PATTERN.fullmatch(normalized_username))
        and normalized_username not in RESERVED_PUBLIC_USERNAMES
    )


async def ensure_public_username(
    db: AsyncSession,
    user: User,
    preferred_username: str | None = None,
) -> None:
    """assign a stable public username if the user does not have one"""
    if user.public_username:
        user.public_username = normalize_public_username(user.public_username)
        return

    user.public_username = await allocate_public_username(db, user.id, preferred_username)


async def allocate_public_username(
    db: AsyncSession,
    user_id: UUID,
    preferred_username: str | None = None,
) -> str:
    """allocate an available public username for a user id"""
    for candidate in _public_username_candidates(user_id, preferred_username):
        if await _public_username_exists(db, candidate):
            continue
        return candidate

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not allocate public username",
    )


def _public_username_candidates(user_id: UUID, preferred_username: str | None) -> list[str]:
    candidates: list[str] = []
    normalized_preferred = normalize_public_username(preferred_username)
    if is_valid_public_username(normalized_preferred):
        candidates.append(normalized_preferred)

    stable_suffix = _base36(user_id.int).lower()
    base = f"u{stable_suffix[:10]}"
    candidates.append(base)
    candidates.extend(f"{base}_{index}" for index in range(2, 10))
    return candidates


async def _public_username_exists(db: AsyncSession, public_username: str) -> bool:
    result = await db.execute(
        select(User.id).where(User.public_username == public_username).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return True
    result = await db.execute(
        select(ProfileUsernameAlias.id)
        .where(ProfileUsernameAlias.username == public_username)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def _base36(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    digits: list[str] = []
    while value:
        value, remainder = divmod(value, 36)
        digits.append(alphabet[remainder])
    return "".join(reversed(digits))


def build_public_profile_url(user: User, settings: Settings | None = None) -> str | None:
    """build canonical public profile URL"""
    public_username = getattr(user, "public_username", None)
    if not public_username:
        return None
    active_settings = settings or get_settings()
    base_url = (
        active_settings.public_web_app_url
        or active_settings.telegram_mini_app_url
        or "http://localhost:3000"
    ).rstrip("/")
    return f"{base_url}/@{public_username}"


def build_telegram_startapp_url(user: User, settings: Settings | None = None) -> str | None:
    """build telegram mini app profile deep link"""
    public_username = getattr(user, "public_username", None)
    if not public_username:
        return None
    active_settings = settings or get_settings()
    bot_username = active_settings.telegram_bot_username.strip().removeprefix("@")
    if not bot_username:
        return None
    return f"https://t.me/{bot_username}?startapp=p_{public_username}"


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
    settings: Settings | None = None,
) -> UserProfileResponse:
    """build user profile response — birthday is shown to anyone who can view the profile"""
    is_owner = current_user is not None and current_user.id == user.id
    return UserProfileResponse(
        user_id=str(user.id),
        username=user.username,
        public_username=getattr(user, "public_username", None),
        public_profile_url=build_public_profile_url(user, settings),
        telegram_startapp_url=build_telegram_startapp_url(user, settings),
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

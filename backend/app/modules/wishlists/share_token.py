"""wishlist share token — Redis-backed, 30-day TTL"""
import secrets
from uuid import UUID

from redis.asyncio import Redis

SHARE_TOKEN_TTL = 30 * 24 * 60 * 60  # 30 days
_PREFIX = "wishlist_share:"


async def create_wishlist_share_token(redis: Redis, wishlist_id: UUID) -> str:
    token = secrets.token_urlsafe(32)
    await redis.setex(f"{_PREFIX}{token}", SHARE_TOKEN_TTL, str(wishlist_id))
    return token


async def validate_wishlist_share_token(
    redis: Redis,
    token: str | None,
    wishlist_id: UUID,
) -> bool:
    if not token:
        return False
    stored = await redis.get(f"{_PREFIX}{token}")
    if not stored:
        return False
    value = stored.decode() if isinstance(stored, bytes) else stored
    return value == str(wishlist_id)

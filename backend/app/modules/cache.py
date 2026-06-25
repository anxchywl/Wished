"""cache-aside helpers for Redis-backed read caching

Strategy: cache frequently-read, infrequently-mutated list responses in Redis.
Writers call cache_delete after a successful DB commit so the next read rebuilds
the cache from the database (lazy load).

TTLs are intentionally shorter than client-side stale times so the server cache
acts as a DB shield, not a consistency layer.
"""
import logging
from typing import TypeVar, Callable, Awaitable

from pydantic import BaseModel
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

WISHLISTS_TTL = 120     # seconds — user's own wishlist list
WISHES_TTL = 120        # seconds — wishes in a single wishlist
FOLLOWING_TTL = 120     # seconds — user's following list


def wishlists_cache_key(user_id: object) -> str:
    return f"cache:wishlists:user:{user_id}"


def wishes_cache_key(wishlist_id: object) -> str:
    return f"cache:wishes:{wishlist_id}"


def following_cache_key(user_id: object) -> str:
    return f"cache:following:{user_id}"


async def cache_get_or_fetch(
    redis: Redis,
    key: str,
    ttl: int,
    model_class: type[T],
    fetch: Callable[[], Awaitable[T]],
) -> T:
    """return cached value if present; otherwise fetch, cache, and return"""
    try:
        raw = await redis.get(key)
        if raw:
            return model_class.model_validate_json(raw)
    except Exception as exc:
        logger.debug("cache read miss or error for key %s: %s", key, exc)

    result = await fetch()

    try:
        await redis.setex(key, ttl, result.model_dump_json())
    except Exception as exc:
        logger.debug("cache write failed for key %s: %s", key, exc)

    return result


async def cache_delete(redis: Redis, *keys: str) -> None:
    """remove one or more cache entries — call after successful DB mutations"""
    if not keys:
        return
    try:
        await redis.delete(*keys)
    except Exception as exc:
        logger.debug("cache delete failed for keys %s: %s", keys, exc)

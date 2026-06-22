"""tests for Redis-backed rate limiters across all modules"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import HTTPException

from app.core.rate_limit import check_rate_limit, check_dual_rate_limit
from app.modules.auth.rate_limit import check_auth_rate_limit_by_telegram_id
from app.modules.wishlists.rate_limit import (
    check_wishlist_create_limit,
    check_wishlist_edit_limit,
    check_wishlist_delete_limit,
)
from app.modules.wishes.rate_limit import (
    check_wish_create_limit,
    check_wish_edit_limit,
    check_wish_delete_limit,
)
from app.modules.users.rate_limit import check_follow_limit, check_unfollow_limit
from app.modules.reservations.rate_limit import (
    check_reservation_create_limit,
    check_reservation_cancel_limit,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _redis_at_count(count: int) -> MagicMock:
    """Redis mock where incr returns `count`"""
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[count, True, count, True])
    redis.pipeline = MagicMock(return_value=pipe)
    return redis


def _redis_under_limit() -> MagicMock:
    return _redis_at_count(1)


def _redis_over_limit(limit: int) -> MagicMock:
    return _redis_at_count(limit + 1)


# ---------------------------------------------------------------------------
# generic rate limiter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_rate_limit_passes_under_limit():
    redis = _redis_at_count(5)
    await check_rate_limit(redis, "test:prefix", "user-1", 60, 10)


@pytest.mark.asyncio
async def test_check_rate_limit_raises_429_over_limit():
    redis = _redis_at_count(11)
    with pytest.raises(HTTPException) as exc_info:
        await check_rate_limit(redis, "test:prefix", "user-1", 60, 10)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_check_dual_rate_limit_passes_under_both():
    redis = _redis_at_count(5)
    await check_dual_rate_limit(redis, "rate:test", "uid", per_hour=10, per_day=100)


@pytest.mark.asyncio
async def test_check_dual_rate_limit_raises_on_hourly_exceeded():
    redis = _redis_at_count(11)
    with pytest.raises(HTTPException) as exc_info:
        await check_dual_rate_limit(redis, "rate:test", "uid", per_hour=10, per_day=100)
    assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# auth per-telegram-id rate limit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_tg_id_rate_limit_passes():
    redis = _redis_at_count(3)
    await check_auth_rate_limit_by_telegram_id(redis, 123456)


@pytest.mark.asyncio
async def test_auth_tg_id_rate_limit_raises_429():
    from app.modules.auth.rate_limit import AUTH_PER_TG_ID_PER_MINUTE
    redis = _redis_at_count(AUTH_PER_TG_ID_PER_MINUTE + 1)
    with pytest.raises(HTTPException) as exc_info:
        await check_auth_rate_limit_by_telegram_id(redis, 123456)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


# ---------------------------------------------------------------------------
# wishlist rate limits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wishlist_create_passes_under_limit():
    redis = _redis_at_count(5)
    await check_wishlist_create_limit(redis, uuid4(), per_hour=20, per_day=100)


@pytest.mark.asyncio
async def test_wishlist_create_raises_over_hourly_limit():
    redis = _redis_at_count(21)
    with pytest.raises(HTTPException) as exc_info:
        await check_wishlist_create_limit(redis, uuid4(), per_hour=20, per_day=100)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_wishlist_edit_passes():
    redis = _redis_at_count(1)
    await check_wishlist_edit_limit(redis, uuid4(), per_hour=100)


@pytest.mark.asyncio
async def test_wishlist_edit_raises_over_limit():
    redis = _redis_at_count(101)
    with pytest.raises(HTTPException) as exc_info:
        await check_wishlist_edit_limit(redis, uuid4(), per_hour=100)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_wishlist_delete_raises_over_limit():
    redis = _redis_at_count(21)
    with pytest.raises(HTTPException) as exc_info:
        await check_wishlist_delete_limit(redis, uuid4(), per_hour=20)
    assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# wish rate limits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wish_create_passes_under_limit():
    redis = _redis_at_count(50)
    await check_wish_create_limit(redis, uuid4(), per_hour=100, per_day=500)


@pytest.mark.asyncio
async def test_wish_create_raises_over_hourly_limit():
    redis = _redis_at_count(101)
    with pytest.raises(HTTPException) as exc_info:
        await check_wish_create_limit(redis, uuid4(), per_hour=100, per_day=500)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_wish_edit_raises_over_limit():
    redis = _redis_at_count(301)
    with pytest.raises(HTTPException) as exc_info:
        await check_wish_edit_limit(redis, uuid4(), per_hour=300)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_wish_delete_raises_over_limit():
    redis = _redis_at_count(101)
    with pytest.raises(HTTPException) as exc_info:
        await check_wish_delete_limit(redis, uuid4(), per_hour=100)
    assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# follow rate limits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_follow_passes_under_limit():
    redis = _redis_at_count(50)
    await check_follow_limit(redis, uuid4(), per_hour=100)


@pytest.mark.asyncio
async def test_follow_raises_over_limit():
    redis = _redis_at_count(101)
    with pytest.raises(HTTPException) as exc_info:
        await check_follow_limit(redis, uuid4(), per_hour=100)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_unfollow_raises_over_limit():
    redis = _redis_at_count(101)
    with pytest.raises(HTTPException) as exc_info:
        await check_unfollow_limit(redis, uuid4(), per_hour=100)
    assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# reservation rate limits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reservation_create_passes_under_limit():
    redis = _redis_at_count(30)
    await check_reservation_create_limit(redis, uuid4(), per_hour=60)


@pytest.mark.asyncio
async def test_reservation_create_raises_over_limit():
    redis = _redis_at_count(61)
    with pytest.raises(HTTPException) as exc_info:
        await check_reservation_create_limit(redis, uuid4(), per_hour=60)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_reservation_cancel_raises_over_limit():
    redis = _redis_at_count(61)
    with pytest.raises(HTTPException) as exc_info:
        await check_reservation_cancel_limit(redis, uuid4(), per_hour=60)
    assert exc_info.value.status_code == 429

"""tests for notification batching and outbound rate limiting"""

import pytest
from unittest.mock import AsyncMock


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_redis(set_result=True):
    """redis mock where `set nx=True` returns set_result"""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True if set_result else None)
    return redis


def _make_redis_outbound(count: int):
    """redis mock for outbound rate limit check"""
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=count)
    redis.expire = AsyncMock(return_value=True)
    return redis


# ---------------------------------------------------------------------------
# _is_batched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_batched_returns_false_on_first_call():
    """first notification for this category+actor+recipient is NOT batched"""
    from app.modules.notifications.handlers import _is_batched

    redis = _make_redis(set_result=True)  # key was newly set
    result = await _is_batched(redis, "wish_created", "actor-1", 99999, 60)
    assert result is False


@pytest.mark.asyncio
async def test_is_batched_returns_true_on_repeat_call():
    """subsequent notification for same category+actor+recipient IS batched"""
    from app.modules.notifications.handlers import _is_batched

    redis = _make_redis(set_result=None)  # key already existed
    result = await _is_batched(redis, "wish_created", "actor-1", 99999, 60)
    assert result is True


# ---------------------------------------------------------------------------
# _check_outbound_rate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_outbound_rate_returns_true_under_limit():
    from app.modules.notifications.handlers import _check_outbound_rate, OUTBOUND_RATE_LIMIT

    redis = _make_redis_outbound(OUTBOUND_RATE_LIMIT - 1)
    result = await _check_outbound_rate(redis)
    assert result is True


@pytest.mark.asyncio
async def test_check_outbound_rate_returns_false_over_limit():
    from app.modules.notifications.handlers import _check_outbound_rate, OUTBOUND_RATE_LIMIT

    redis = _make_redis_outbound(OUTBOUND_RATE_LIMIT + 1)
    result = await _check_outbound_rate(redis)
    assert result is False


# ---------------------------------------------------------------------------
# _is_duplicate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_duplicate_returns_false_on_first_send():
    from app.modules.notifications.handlers import _is_duplicate

    redis = _make_redis(set_result=True)
    result = await _is_duplicate(redis, "event-abc", 12345)
    assert result is False


@pytest.mark.asyncio
async def test_is_duplicate_returns_true_on_repeat():
    from app.modules.notifications.handlers import _is_duplicate

    redis = _make_redis(set_result=None)  # key already existed
    result = await _is_duplicate(redis, "event-abc", 12345)
    assert result is True

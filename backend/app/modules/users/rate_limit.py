"""follow/unfollow rate limits backed by Redis"""

import logging
from uuid import UUID

from redis.asyncio import Redis

from app.core.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)


async def check_follow_limit(redis: Redis, user_id: UUID, per_hour: int) -> None:
    uid = str(user_id)
    await check_rate_limit(
        redis,
        "rate:follow:hr",
        uid,
        3600,
        per_hour,
        detail="follow rate limit exceeded — try again later",
    )


async def check_unfollow_limit(redis: Redis, user_id: UUID, per_hour: int) -> None:
    uid = str(user_id)
    await check_rate_limit(
        redis,
        "rate:unfollow:hr",
        uid,
        3600,
        per_hour,
        detail="unfollow rate limit exceeded — try again later",
    )


async def check_public_username_resolve_limit(redis: Redis, user_id: UUID, per_hour: int) -> None:
    uid = str(user_id)
    await check_rate_limit(
        redis,
        "rate:public_username_resolve:hr",
        uid,
        3600,
        per_hour,
        detail="public username lookup rate limit exceeded — try again later",
    )

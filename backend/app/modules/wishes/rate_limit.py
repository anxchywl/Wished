"""wish mutation rate limits backed by Redis"""

import logging
from uuid import UUID

from redis.asyncio import Redis

from app.core.rate_limit import check_dual_rate_limit, check_rate_limit

logger = logging.getLogger(__name__)


async def check_wish_create_limit(redis: Redis, user_id: UUID, per_hour: int, per_day: int) -> None:
    uid = str(user_id)
    await check_dual_rate_limit(redis, "rate:wish:create", uid, per_hour, per_day, "wish creation ")


async def check_wish_edit_limit(redis: Redis, user_id: UUID, per_hour: int) -> None:
    uid = str(user_id)
    await check_rate_limit(
        redis, "rate:wish:edit:hr", uid, 3600, per_hour,
        detail="wish edit rate limit exceeded — try again later",
    )


async def check_wish_delete_limit(redis: Redis, user_id: UUID, per_hour: int) -> None:
    uid = str(user_id)
    await check_rate_limit(
        redis, "rate:wish:delete:hr", uid, 3600, per_hour,
        detail="wish delete rate limit exceeded — try again later",
    )

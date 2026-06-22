"""reservation rate limits backed by Redis"""

import logging
from uuid import UUID

from redis.asyncio import Redis

from app.core.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)


async def check_reservation_create_limit(redis: Redis, user_id: UUID, per_hour: int) -> None:
    uid = str(user_id)
    await check_rate_limit(
        redis, "rate:reservation:create:hr", uid, 3600, per_hour,
        detail="reservation rate limit exceeded — try again later",
    )


async def check_reservation_cancel_limit(redis: Redis, user_id: UUID, per_hour: int) -> None:
    uid = str(user_id)
    await check_rate_limit(
        redis, "rate:reservation:cancel:hr", uid, 3600, per_hour,
        detail="reservation cancel rate limit exceeded — try again later",
    )

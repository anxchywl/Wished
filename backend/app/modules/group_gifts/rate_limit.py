"""group gift mutation rate limits backed by Redis"""

from uuid import UUID

from redis.asyncio import Redis

from app.core.rate_limit import check_dual_rate_limit, check_rate_limit


async def check_gift_create_limit(redis: Redis, user_id: UUID) -> None:
    uid = str(user_id)
    await check_dual_rate_limit(redis, "rate:gg:create", uid, 15, 50, "group gift creation ")


async def check_contribution_create_limit(redis: Redis, user_id: UUID) -> None:
    uid = str(user_id)
    await check_rate_limit(
        redis, "rate:gg:join:hr", uid, 3600, 40,
        detail="contribution rate limit exceeded — try again later",
    )

"""upload rate limiting backed by Redis fixed-window counters"""

from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis

UPLOADS_PER_MINUTE = 20
UPLOADS_PER_HOUR = 100


async def check_upload_rate_limit(redis: Redis, user_id: UUID) -> None:
    """increment upload counters and raise 429 if either limit is exceeded"""
    uid = str(user_id)
    per_minute_key = f"media:upload:min:{uid}"
    per_hour_key = f"media:upload:hr:{uid}"

    async with redis.pipeline(transaction=False) as pipe:
        pipe.incr(per_minute_key)
        pipe.expire(per_minute_key, 60)
        pipe.incr(per_hour_key)
        pipe.expire(per_hour_key, 3600)
        results = await pipe.execute()

    minute_count: int = results[0]
    hour_count: int = results[2]

    if minute_count > UPLOADS_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="upload rate limit exceeded — try again in a minute",
        )
    if hour_count > UPLOADS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="upload rate limit exceeded — try again later",
        )

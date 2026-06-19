"""auth endpoint rate limiting backed by Redis fixed-window counters"""

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

AUTH_REQUESTS_PER_MINUTE = 10
AUTH_REQUESTS_PER_HOUR = 100


async def check_auth_rate_limit(redis: Redis, request: Request) -> None:
    """increment auth counters per client IP and raise 429 if either limit is exceeded"""
    # prefer the forwarded IP when behind a trusted proxy
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    safe_ip = client_ip.replace(":", "_")

    per_minute_key = f"auth:rate:min:{safe_ip}"
    per_hour_key = f"auth:rate:hr:{safe_ip}"

    async with redis.pipeline(transaction=False) as pipe:
        pipe.incr(per_minute_key)
        pipe.expire(per_minute_key, 60)
        pipe.incr(per_hour_key)
        pipe.expire(per_hour_key, 3600)
        results = await pipe.execute()

    minute_count: int = results[0]
    hour_count: int = results[2]

    if minute_count > AUTH_REQUESTS_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many authentication requests — try again in a minute",
            headers={"Retry-After": "60"},
        )
    if hour_count > AUTH_REQUESTS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many authentication requests — try again later",
            headers={"Retry-After": "3600"},
        )

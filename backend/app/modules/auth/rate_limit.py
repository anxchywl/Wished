"""auth endpoint rate limiting backed by Redis fixed-window counters"""

import logging

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

AUTH_REQUESTS_PER_MINUTE = 10
AUTH_REQUESTS_PER_HOUR = 100
AUTH_PER_TG_ID_PER_MINUTE = 5

logger = logging.getLogger(__name__)


async def check_auth_rate_limit(redis: Redis, request: Request, trust_proxy_headers: bool = False) -> None:
    """increment auth counters per client IP and raise 429 if either limit is exceeded

    trust_proxy_headers must only be True when the backend sits behind a trusted
    reverse proxy that sanitises X-Forwarded-For. When False (default), the direct
    TCP connection address is used so that clients cannot bypass the limit by
    forging the header.
    """
    if trust_proxy_headers:
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
    else:
        client_ip = request.client.host if request.client else "unknown"
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
        logger.warning("auth rate limit (IP/min) hit from ip=%s count=%d", safe_ip, minute_count)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many authentication requests — try again in a minute",
            headers={"Retry-After": "60"},
        )
    if hour_count > AUTH_REQUESTS_PER_HOUR:
        logger.warning("auth rate limit (IP/hr) hit from ip=%s count=%d", safe_ip, hour_count)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many authentication requests — try again later",
            headers={"Retry-After": "3600"},
        )


async def check_auth_rate_limit_by_telegram_id(redis: Redis, telegram_id: int) -> None:
    """after validating init_data, enforce per-Telegram-ID rate limit to prevent replay abuse"""
    key = f"auth:rate:tg:{telegram_id}"
    async with redis.pipeline(transaction=False) as pipe:
        pipe.incr(key)
        pipe.expire(key, 60)
        results = await pipe.execute()

    count: int = results[0]
    if count > AUTH_PER_TG_ID_PER_MINUTE:
        logger.warning("auth rate limit (TG ID/min) hit telegram_id=%d count=%d", telegram_id, count)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many authentication requests — try again in a minute",
            headers={"Retry-After": "60"},
        )

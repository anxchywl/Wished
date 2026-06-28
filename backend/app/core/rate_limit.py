"""shared Redis fixed-window rate limiter used across all modules"""

from fastapi import HTTPException, status
from redis.asyncio import Redis


async def check_rate_limit(
    redis: Redis,
    key_prefix: str,
    identifier: str,
    window_seconds: int,
    max_requests: int,
    retry_after: int | None = None,
    detail: str | None = None,
) -> None:
    """increment a fixed-window counter and raise 429 if the limit is exceeded"""
    key = f"{key_prefix}:{identifier}"
    async with redis.pipeline(transaction=False) as pipe:
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()

    count: int = results[0]
    if count > max_requests:
        headers = {"Retry-After": str(retry_after or window_seconds)}
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail or "rate limit exceeded — try again later",
            headers=headers,
        )


async def check_dual_rate_limit(
    redis: Redis,
    key_prefix: str,
    identifier: str,
    per_hour: int,
    per_day: int | None = None,
    extra_detail: str = "",
) -> None:
    """check hourly and optional daily fixed-window rate limits"""
    hour_key = f"{key_prefix}:hr:{identifier}"
    keys_and_windows: list[tuple[str, int, int]] = [(hour_key, 3600, per_hour)]
    if per_day is not None:
        day_key = f"{key_prefix}:day:{identifier}"
        keys_and_windows.append((day_key, 86400, per_day))

    cmds: list[tuple[str, int]] = []
    async with redis.pipeline(transaction=False) as pipe:
        for key, window, _ in keys_and_windows:
            pipe.incr(key)
            pipe.expire(key, window)
            cmds.append((key, window))
        results = await pipe.execute()

    # results layout: [count1, expire1, count2, expire2, ...]
    for i, (_key, _window, limit) in enumerate(keys_and_windows):
        count: int = results[i * 2]
        if count > limit:
            period = "hour" if i == 0 else "day"
            retry = 3600 if i == 0 else 86400
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"rate limit exceeded — too many {extra_detail}requests this {period}",
                headers={"Retry-After": str(retry)},
            )

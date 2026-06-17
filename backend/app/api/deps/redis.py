from collections.abc import AsyncGenerator

from redis.asyncio import Redis

from app.integrations.redis import get_redis_client


async def get_redis() -> AsyncGenerator[Redis, None]:
    """load redis dependency"""
    client = get_redis_client()
    yield client

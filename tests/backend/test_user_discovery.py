"""user discovery tests"""

import pytest

from app.modules.users.discovery import (
    DISCOVERY_TOKEN_TTL_SECONDS,
    create_discovery_token,
    validate_discovery_token,
)


@pytest.mark.asyncio
async def test_discovery_token_is_bound_to_requester_and_target() -> None:
    """test discovery token binding"""
    redis = FakeRedis()

    token = await create_discovery_token(redis, 100, 200)

    assert redis.ttl == DISCOVERY_TOKEN_TTL_SECONDS
    assert await validate_discovery_token(redis, token, 100, 200) is True
    assert await validate_discovery_token(redis, token, 101, 200) is False
    assert await validate_discovery_token(redis, token, 100, 201) is False
    assert await validate_discovery_token(redis, token, 200, 200) is False


class FakeRedis:
    """fake discovery storage"""

    def __init__(self) -> None:
        self.values = {}
        self.ttl = None

    async def setex(self, key, ttl, value) -> None:
        """store token"""
        self.values[key] = value
        self.ttl = ttl

    async def get(self, key):
        """read token"""
        return self.values.get(key)

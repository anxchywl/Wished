"""user discovery access"""
import json
import secrets

from redis.asyncio import Redis

DISCOVERY_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


async def create_discovery_token(
    redis: Redis,
    requester_telegram_id: int,
    target_telegram_id: int,
) -> str:
    """create temporary discovery access"""
    token = secrets.token_urlsafe(24)
    payload = json.dumps(
        {
            "requester_telegram_id": requester_telegram_id,
            "target_telegram_id": target_telegram_id,
        }
    )
    await redis.setex(
        f"discovery:{token}",
        DISCOVERY_TOKEN_TTL_SECONDS,
        payload,
    )
    return token


async def validate_discovery_token(
    redis: Redis,
    token: str | None,
    requester_telegram_id: int,
    target_telegram_id: int,
) -> bool:
    """validate temporary discovery access"""
    if not token:
        return False

    raw_payload = await redis.get(f"discovery:{token}")
    if not raw_payload:
        return False

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return False

    return (
        payload.get("requester_telegram_id") == requester_telegram_id
        and payload.get("target_telegram_id") == target_telegram_id
        and requester_telegram_id != target_telegram_id
    )

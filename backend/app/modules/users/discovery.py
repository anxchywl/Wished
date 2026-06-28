"""user discovery access — PostgreSQL is source of truth; Redis is a TTL cache"""

import json
import secrets
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.discovery_tokens import DiscoveryToken

DISCOVERY_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


async def create_discovery_token(
    redis: Redis,
    requester_telegram_id: int,
    target_telegram_id: int,
    db: AsyncSession | None = None,
) -> str:
    """create temporary discovery access token, persisted to PostgreSQL"""
    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(UTC) + timedelta(seconds=DISCOVERY_TOKEN_TTL_SECONDS)

    if db is not None:
        record = DiscoveryToken(
            token=token,
            requester_telegram_id=requester_telegram_id,
            target_telegram_id=target_telegram_id,
            expires_at=expires_at,
        )
        db.add(record)
        await db.commit()

    # cache in Redis for fast validation path
    payload = json.dumps(
        {
            "requester_telegram_id": requester_telegram_id,
            "target_telegram_id": target_telegram_id,
        }
    )
    await redis.setex(f"discovery:{token}", DISCOVERY_TOKEN_TTL_SECONDS, payload)

    return token


async def validate_discovery_token(
    redis: Redis,
    token: str | None,
    requester_telegram_id: int,
    target_telegram_id: int,
    db: AsyncSession | None = None,
) -> bool:
    """validate discovery access token — checks Redis cache first, falls back to PostgreSQL"""
    if not token:
        return False

    # fast path: Redis cache hit
    raw_payload = await redis.get(f"discovery:{token}")
    if raw_payload:
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return False
        return (
            payload.get("requester_telegram_id") == requester_telegram_id
            and payload.get("target_telegram_id") == target_telegram_id
            and requester_telegram_id != target_telegram_id
        )

    # slow path: Redis miss — check PostgreSQL (handles Redis restarts)
    if db is None:
        return False

    now = datetime.now(UTC)
    result = await db.execute(
        select(DiscoveryToken).where(
            DiscoveryToken.token == token,
            DiscoveryToken.requester_telegram_id == requester_telegram_id,
            DiscoveryToken.target_telegram_id == target_telegram_id,
            DiscoveryToken.expires_at > now,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return False

    # re-populate Redis cache so subsequent requests are fast
    remaining_ttl = int((record.expires_at - now).total_seconds())
    if remaining_ttl > 0:
        payload = json.dumps(
            {
                "requester_telegram_id": requester_telegram_id,
                "target_telegram_id": target_telegram_id,
            }
        )
        await redis.setex(f"discovery:{token}", remaining_ttl, payload)

    return requester_telegram_id != target_telegram_id

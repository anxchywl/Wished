import json
import logging
from uuid import UUID, uuid4

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

QUEUE_KEY = "notifications:queue"


async def publish_event(redis: Redis, event_type: str, payload: dict) -> None:
    """publish domain event to notification queue — failures are non-fatal"""
    try:
        data = {"type": event_type, "event_id": str(uuid4()), **_serialize(payload)}
        await redis.rpush(QUEUE_KEY, json.dumps(data))
    except Exception:
        logger.exception("failed to publish event type=%s", event_type)


def _serialize(obj: object) -> object:
    """convert UUIDs to strings for JSON serialization"""
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, UUID):
        return str(obj)
    return obj

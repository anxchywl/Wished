import asyncio
import json
import logging

from aiogram import Bot
from redis.asyncio import Redis

from app.modules.notifications.handlers import (
    handle_followed,
    handle_wish_created,
    handle_wish_fulfilled,
    handle_wishlist_created,
)

logger = logging.getLogger(__name__)

QUEUE_KEY = "notifications:queue"
BLPOP_TIMEOUT = 5

_HANDLERS = {
    "FOLLOWED": handle_followed,
    "WISHLIST_CREATED": handle_wishlist_created,
    "WISH_CREATED": handle_wish_created,
    "WISH_FULFILLED": handle_wish_fulfilled,
}


async def run_notification_worker(
    redis: Redis,
    bot: Bot,
    session_factory,
    mini_app_url: str,
) -> None:
    """consume notification events from redis queue and dispatch to telegram"""
    logger.info("notification worker started")
    while True:
        try:
            item = await redis.blpop(QUEUE_KEY, timeout=BLPOP_TIMEOUT)
            if item is None:
                continue
            _, raw = item
            event = json.loads(raw)
            event_type = event.get("type")
            handler = _HANDLERS.get(event_type)
            if handler is None:
                logger.warning("unknown notification event type: %s", event_type)
                continue

            async with session_factory() as db:
                try:
                    await handler(event, db, bot, redis, mini_app_url)
                except Exception:
                    logger.exception("notification handler failed for event_type=%s event_id=%s", event_type, event.get("event_id"))
        except asyncio.CancelledError:
            logger.info("notification worker cancelled")
            break
        except Exception:
            logger.exception("notification worker error — retrying")
            await asyncio.sleep(1)

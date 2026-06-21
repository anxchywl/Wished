import logging
from uuid import UUID

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Follow, User, Wish, Wishlist
from app.modules.notifications.deep_links import profile_url, wish_url, wishlist_url

logger = logging.getLogger(__name__)

DEDUP_TTL_SECONDS = 172800  # 48 hours

_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "followed_title": "New follower",
        "followed_body": "{actor} started following you.",
        "open_profile": "Open Profile",
        "wishlist_created_title": "New wishlist",
        "wishlist_created_body": "{actor} created a new wishlist.\n{title}",
        "open_wishlist": "Open Wishlist",
        "wish_created_title": "New wish",
        "wish_created_body": "{actor} added a new wish.\n{title}",
        "open_wish": "Open Wish",
        "wish_fulfilled_title": "Wish fulfilled",
        "wish_fulfilled_body": "{actor} marked a wish as fulfilled.\n{title}",
    },
    "ru": {
        "followed_title": "Новый подписчик",
        "followed_body": "{actor} начал(а) следить за вами.",
        "open_profile": "Открыть профиль",
        "wishlist_created_title": "Новый список желаний",
        "wishlist_created_body": "{actor} создал(а) новый список желаний.\n{title}",
        "open_wishlist": "Открыть список",
        "wish_created_title": "Новое желание",
        "wish_created_body": "{actor} добавил(а) новое желание.\n{title}",
        "open_wish": "Открыть желание",
        "wish_fulfilled_title": "Желание исполнено",
        "wish_fulfilled_body": "{actor} отметил(а) желание как исполненное.\n{title}",
    },
    "kz": {
        "followed_title": "Жаңа жазылушы",
        "followed_body": "{actor} сізді бақылай бастады.",
        "open_profile": "Профильді ашу",
        "wishlist_created_title": "Жаңа тілектер тізімі",
        "wishlist_created_body": "{actor} жаңа тілектер тізімін жасады.\n{title}",
        "open_wishlist": "Тізімді ашу",
        "wish_created_title": "Жаңа тілек",
        "wish_created_body": "{actor} жаңа тілек қосты.\n{title}",
        "open_wish": "Тілекті ашу",
        "wish_fulfilled_title": "Тілек орындалды",
        "wish_fulfilled_body": "{actor} тілекті орындалды деп белгіледі.\n{title}",
    },
}


def _text(language_code: str | None) -> dict[str, str]:
    lang = language_code or "en"
    if lang in {"kk", "kz"}:
        lang = "kz"
    return _TEXT.get(lang, _TEXT["en"])


def _actor_name(user: User) -> str:
    parts = [p for p in [user.first_name, user.last_name] if p]
    if parts:
        return " ".join(parts)
    if user.username:
        return f"@{user.username}"
    return "Someone"


async def _is_duplicate(redis: Redis, event_id: str, telegram_id: int) -> bool:
    """return True if this notification was already sent"""
    key = f"notif:dedup:{event_id}:{telegram_id}"
    result = await redis.set(key, "1", nx=True, ex=DEDUP_TTL_SECONDS)
    # result is None if key already existed
    return result is None


async def _send(bot: Bot, telegram_id: int, text: str, button_text: str, url: str) -> None:
    """send telegram DM with a single mini app button"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button_text, web_app=WebAppInfo(url=url))]
        ]
    )
    await bot.send_message(chat_id=telegram_id, text=text, reply_markup=keyboard)


async def handle_followed(
    event: dict,
    db: AsyncSession,
    bot: Bot,
    redis: Redis,
    mini_app_url: str,
) -> None:
    """notify followed user when someone follows them"""
    follower_id = UUID(event["follower_user_id"])
    followed_id = UUID(event["followed_user_id"])
    event_id = event["event_id"]

    result = await db.execute(select(User).where(User.id == follower_id))
    follower = result.scalar_one_or_none()
    if follower is None:
        return

    result = await db.execute(select(User).where(User.id == followed_id))
    followed = result.scalar_one_or_none()
    if followed is None or followed.telegram_id is None:
        return

    if await _is_duplicate(redis, event_id, followed.telegram_id):
        return

    t = _text(followed.language_code)
    actor = _actor_name(follower)
    text = t['followed_body'].format(actor=actor)
    url = profile_url(mini_app_url, follower.username or str(follower_id))
    try:
        await _send(bot, followed.telegram_id, text, t["open_profile"], url)
        logger.info("sent FOLLOWED notification to telegram_id=%s", followed.telegram_id)
    except Exception:
        logger.exception("failed to send FOLLOWED notification to telegram_id=%s", followed.telegram_id)


async def handle_wishlist_created(
    event: dict,
    db: AsyncSession,
    bot: Bot,
    redis: Redis,
    mini_app_url: str,
) -> None:
    """notify followers when a user creates a wishlist"""
    wishlist_id = UUID(event["wishlist_id"])
    owner_id = UUID(event["owner_user_id"])
    event_id = event["event_id"]

    result = await db.execute(select(User).where(User.id == owner_id))
    owner = result.scalar_one_or_none()
    if owner is None:
        return

    result = await db.execute(select(Wishlist).where(Wishlist.id == wishlist_id))
    wishlist = result.scalar_one_or_none()
    if wishlist is None or wishlist.visibility != "public":
        return

    followers = await _get_followers(db, owner_id)
    actor = _actor_name(owner)
    username = owner.username or str(owner_id)
    url = wishlist_url(mini_app_url, username, wishlist_id)

    for follower_tg_id, language_code in followers:
        if await _is_duplicate(redis, event_id, follower_tg_id):
            continue
        t = _text(language_code)
        text = t['wishlist_created_body'].format(actor=actor, title=wishlist.title)
        try:
            await _send(bot, follower_tg_id, text, t["open_wishlist"], url)
            logger.info("sent WISHLIST_CREATED notification to telegram_id=%s", follower_tg_id)
        except Exception:
            logger.exception("failed to send WISHLIST_CREATED notification to telegram_id=%s", follower_tg_id)


async def handle_wish_created(
    event: dict,
    db: AsyncSession,
    bot: Bot,
    redis: Redis,
    mini_app_url: str,
) -> None:
    """notify followers when a user adds a wish"""
    wish_id = UUID(event["wish_id"])
    wishlist_id = UUID(event["wishlist_id"])
    owner_id = UUID(event["owner_user_id"])
    event_id = event["event_id"]

    result = await db.execute(select(User).where(User.id == owner_id))
    owner = result.scalar_one_or_none()
    if owner is None:
        return

    result = await db.execute(select(Wishlist).where(Wishlist.id == wishlist_id))
    wishlist = result.scalar_one_or_none()
    if wishlist is None or wishlist.visibility != "public":
        return

    result = await db.execute(select(Wish).where(Wish.id == wish_id))
    wish = result.scalar_one_or_none()
    if wish is None:
        return

    followers = await _get_followers(db, owner_id)
    actor = _actor_name(owner)
    username = owner.username or str(owner_id)
    url = wish_url(mini_app_url, username, wishlist_id, wish_id)

    for follower_tg_id, language_code in followers:
        if await _is_duplicate(redis, event_id, follower_tg_id):
            continue
        t = _text(language_code)
        text = t['wish_created_body'].format(actor=actor, title=wish.title)
        try:
            await _send(bot, follower_tg_id, text, t["open_wish"], url)
            logger.info("sent WISH_CREATED notification to telegram_id=%s", follower_tg_id)
        except Exception:
            logger.exception("failed to send WISH_CREATED notification to telegram_id=%s", follower_tg_id)


async def handle_wish_fulfilled(
    event: dict,
    db: AsyncSession,
    bot: Bot,
    redis: Redis,
    mini_app_url: str,
) -> None:
    """notify followers when an owner marks a wish as fulfilled"""
    wish_id = UUID(event["wish_id"])
    wishlist_id = UUID(event["wishlist_id"])
    owner_id = UUID(event["owner_user_id"])
    event_id = event["event_id"]

    result = await db.execute(select(User).where(User.id == owner_id))
    owner = result.scalar_one_or_none()
    if owner is None:
        return

    result = await db.execute(select(Wishlist).where(Wishlist.id == wishlist_id))
    wishlist = result.scalar_one_or_none()
    if wishlist is None or wishlist.visibility != "public":
        return

    result = await db.execute(select(Wish).where(Wish.id == wish_id))
    wish = result.scalar_one_or_none()
    if wish is None:
        return

    followers = await _get_followers(db, owner_id)
    actor = _actor_name(owner)
    username = owner.username or str(owner_id)
    url = wishlist_url(mini_app_url, username, wishlist_id)

    for follower_tg_id, language_code in followers:
        if await _is_duplicate(redis, event_id, follower_tg_id):
            continue
        t = _text(language_code)
        text = t['wish_fulfilled_body'].format(actor=actor, title=wish.title)
        try:
            await _send(bot, follower_tg_id, text, t["open_wishlist"], url)
            logger.info("sent WISH_FULFILLED notification to telegram_id=%s", follower_tg_id)
        except Exception:
            logger.exception("failed to send WISH_FULFILLED notification to telegram_id=%s", follower_tg_id)


async def _get_followers(db: AsyncSession, owner_id: UUID) -> list[tuple[int, str | None]]:
    """return (telegram_id, language_code) for all followers of owner"""
    result = await db.execute(
        select(User.telegram_id, User.language_code)
        .join(Follow, Follow.follower_user_id == User.id)
        .where(Follow.followed_user_id == owner_id)
    )
    return list(result.all())

import logging
from uuid import UUID

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Follow, User, Wish, Wishlist
from app.modules.notifications.deep_links import (
    profile_url_by_id,
    wish_url_by_id,
    wishlist_url_by_id,
)

logger = logging.getLogger(__name__)

DEDUP_TTL_SECONDS = 172800  # 48 hours
BATCH_WINDOW_SECONDS = 60  # suppress rapid same-category notifications per actor→recipient pair
OUTBOUND_RATE_KEY = "notif:outbound:rate"
OUTBOUND_RATE_LIMIT = 25  # max outbound messages per second to stay under Telegram flood limits

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
        "fulfilled_booking_body": "Your gift has been marked as fulfilled. Thank you for making it happen!",
        "fulfilled_group_gift_body": "Your Group Gift has been fulfilled. Thank you for contributing!",
        "gg_transfer_reported_body": "{contributor} reported a transfer.\nAmount: {amount} {currency}\nWish: {wish_title}",
        "gg_confirm_btn": "Confirm",
        "gg_reject_btn": "Reject",
        "gg_transfer_confirmed_body": "Your transfer was confirmed.\nWish: {wish_title}\nProgress: {percent}%",
        "gg_transfer_rejected_body": "Your transfer could not be confirmed.\nWish: {wish_title}\nPlease transfer the amount again and tap 'I have transferred'.",
        "gg_completed_organizer_immediate": "The group gift is complete.\nWish: {wish_title}\nTotal collected: {amount} {currency}",
        "gg_completed_organizer_commit": "The goal has been reached.\nWish: {wish_title}\nTotal pledged: {amount} {currency}\n\nCollect transfers via:\n{payment_method}: {payment_phone}",
        "gg_completed_contributor_immediate": "The group gift is complete.\nWish: {wish_title}",
        "gg_completed_contributor_commit": "The goal has been reached.\nWish: {wish_title}\n\nPlease transfer your pledge to the organizer:\n{payment_method}: {payment_phone}",
        "gg_gift_started_body": "Someone started a group gift for your wish '{wish_title}'.",
        "gg_open_gift": "Open Gift",
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
        "fulfilled_booking_body": "Ваш подарок отмечен как исполненный. Спасибо, что помогли!",
        "fulfilled_group_gift_body": "Ваш групповой подарок исполнен. Спасибо за участие!",
        "gg_transfer_reported_body": "{contributor} сообщил(а) о переводе.\nСумма: {amount} {currency}\nЖелание: {wish_title}",
        "gg_confirm_btn": "Подтвердить",
        "gg_reject_btn": "Отклонить",
        "gg_transfer_confirmed_body": "Ваш перевод подтверждён.\nЖелание: {wish_title}\nПрогресс: {percent}%",
        "gg_transfer_rejected_body": "Ваш перевод не удалось подтвердить.\nЖелание: {wish_title}\nПожалуйста, переведите сумму снова и нажмите «Я перевёл(а)».",
        "gg_completed_organizer_immediate": "Групповой подарок завершён.\nЖелание: {wish_title}\nВсего собрано: {amount} {currency}",
        "gg_completed_organizer_commit": "Цель достигнута.\nЖелание: {wish_title}\nВсего обещано: {amount} {currency}\n\nПолучите переводы через:\n{payment_method}: {payment_phone}",
        "gg_completed_contributor_immediate": "Групповой подарок завершён.\nЖелание: {wish_title}",
        "gg_completed_contributor_commit": "Цель достигнута.\nЖелание: {wish_title}\n\nПожалуйста, переведите вашу долю организатору:\n{payment_method}: {payment_phone}",
        "gg_gift_started_body": "Кто-то начал групповой подарок на ваше желание «{wish_title}».",
        "gg_open_gift": "Открыть подарок",
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
        "fulfilled_booking_body": "Сыйлығыңыз орындалды деп белгіленді. Оны жүзеге асырғаныңызға рахмет!",
        "fulfilled_group_gift_body": "Топтық сыйлығыңыз орындалды. Қатысқаныңызға рахмет!",
        "gg_transfer_reported_body": "{contributor} аударым туралы хабарлады.\nСома: {amount} {currency}\nТілек: {wish_title}",
        "gg_confirm_btn": "Растау",
        "gg_reject_btn": "Қабылдамау",
        "gg_transfer_confirmed_body": "Сіздің аударымыңыз расталды.\nТілек: {wish_title}\nПрогресс: {percent}%",
        "gg_transfer_rejected_body": "Сіздің аударымыңызды растау мүмкін болмады.\nТілек: {wish_title}\nСоманы қайта аударып, «Аударым жасадым» батырмасын басыңыз.",
        "gg_completed_organizer_immediate": "Топтық сыйлық аяқталды.\nТілек: {wish_title}\nЖалпы жиналды: {amount} {currency}",
        "gg_completed_organizer_commit": "Мақсатқа жетілді.\nТілек: {wish_title}\nЖалпы уәде: {amount} {currency}\n\nАударымдарды қабылдаңыз:\n{payment_method}: {payment_phone}",
        "gg_completed_contributor_immediate": "Топтық сыйлық аяқталды.\nТілек: {wish_title}",
        "gg_completed_contributor_commit": "Мақсатқа жетілді.\nТілек: {wish_title}\n\nҮлесіңізді ұйымдастырушыға аударыңыз:\n{payment_method}: {payment_phone}",
        "gg_gift_started_body": "Біреу '{wish_title}' тілегіңізге топтық сыйлық бастады.",
        "gg_open_gift": "Сыйлықты ашу",
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


async def _is_batched(
    redis: Redis, category: str, actor_id: str, recipient_tg_id: int, window: int
) -> bool:
    """return True if a notification for this category+actor was already sent to this recipient recently

    sets the key on first call so subsequent calls within `window` seconds return True.
    """
    key = f"notif:batch:{category}:{actor_id}:{recipient_tg_id}"
    result = await redis.set(key, "1", nx=True, ex=window)
    return result is None


async def _check_outbound_rate(redis: Redis) -> bool:
    """return False if the outbound Telegram rate limit is exceeded (Telegram flood protection)"""
    count = await redis.incr(OUTBOUND_RATE_KEY)
    if count == 1:
        await redis.expire(OUTBOUND_RATE_KEY, 1)
    return count <= OUTBOUND_RATE_LIMIT


async def _send(bot: Bot, telegram_id: int, text: str, button_text: str, url: str) -> None:
    """send telegram DM with a single mini app button"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=button_text, web_app=WebAppInfo(url=url))]]
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
    text = t["followed_body"].format(actor=actor)
    url = profile_url_by_id(mini_app_url, follower_id)
    try:
        await _send(bot, followed.telegram_id, text, t["open_profile"], url)
        logger.info("sent FOLLOWED notification to telegram_id=%s", followed.telegram_id)
    except Exception:
        logger.exception(
            "failed to send FOLLOWED notification to telegram_id=%s", followed.telegram_id
        )


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
    url = wishlist_url_by_id(mini_app_url, owner_id, wishlist_id)

    for follower_tg_id, language_code in followers:
        if await _is_duplicate(redis, event_id, follower_tg_id):
            continue
        if await _is_batched(
            redis, "wishlist_created", str(owner_id), follower_tg_id, BATCH_WINDOW_SECONDS
        ):
            logger.debug("batched WISHLIST_CREATED notification for telegram_id=%s", follower_tg_id)
            continue
        if not await _check_outbound_rate(redis):
            logger.warning(
                "outbound Telegram rate limit hit — dropping WISHLIST_CREATED for telegram_id=%s",
                follower_tg_id,
            )
            continue
        t = _text(language_code)
        text = t["wishlist_created_body"].format(actor=actor, title=wishlist.title)
        try:
            await _send(bot, follower_tg_id, text, t["open_wishlist"], url)
            logger.info("sent WISHLIST_CREATED notification to telegram_id=%s", follower_tg_id)
        except Exception:
            logger.exception(
                "failed to send WISHLIST_CREATED notification to telegram_id=%s", follower_tg_id
            )


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
    url = wish_url_by_id(mini_app_url, owner_id, wishlist_id, wish_id)

    for follower_tg_id, language_code in followers:
        if await _is_duplicate(redis, event_id, follower_tg_id):
            continue
        if await _is_batched(
            redis, "wish_created", str(owner_id), follower_tg_id, BATCH_WINDOW_SECONDS
        ):
            logger.debug("batched WISH_CREATED notification for telegram_id=%s", follower_tg_id)
            continue
        if not await _check_outbound_rate(redis):
            logger.warning(
                "outbound Telegram rate limit hit — dropping WISH_CREATED for telegram_id=%s",
                follower_tg_id,
            )
            continue
        t = _text(language_code)
        text = t["wish_created_body"].format(actor=actor, title=wish.title)
        try:
            await _send(bot, follower_tg_id, text, t["open_wish"], url)
            logger.info("sent WISH_CREATED notification to telegram_id=%s", follower_tg_id)
        except Exception:
            logger.exception(
                "failed to send WISH_CREATED notification to telegram_id=%s", follower_tg_id
            )


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
    url = wishlist_url_by_id(mini_app_url, owner_id, wishlist_id)

    for follower_tg_id, language_code in followers:
        if await _is_duplicate(redis, event_id, follower_tg_id):
            continue
        if await _is_batched(
            redis, "wish_fulfilled", str(owner_id), follower_tg_id, BATCH_WINDOW_SECONDS
        ):
            logger.debug("batched WISH_FULFILLED notification for telegram_id=%s", follower_tg_id)
            continue
        if not await _check_outbound_rate(redis):
            logger.warning(
                "outbound Telegram rate limit hit — dropping WISH_FULFILLED for telegram_id=%s",
                follower_tg_id,
            )
            continue
        t = _text(language_code)
        text = t["wish_fulfilled_body"].format(actor=actor, title=wish.title)
        try:
            await _send(bot, follower_tg_id, text, t["open_wishlist"], url)
            logger.info("sent WISH_FULFILLED notification to telegram_id=%s", follower_tg_id)
        except Exception:
            logger.exception(
                "failed to send WISH_FULFILLED notification to telegram_id=%s", follower_tg_id
            )


async def handle_fulfilled_participant(
    event: dict,
    db: AsyncSession,
    bot: Bot,
    redis: Redis,
    mini_app_url: str,
) -> None:
    """notify the participant who helped fulfill a wish"""
    participant_id = UUID(event["participant_user_id"])
    event_id = event["event_id"]

    result = await db.execute(select(User).where(User.id == participant_id))
    participant = result.scalar_one_or_none()
    if participant is None or participant.telegram_id is None:
        return

    if await _is_duplicate(redis, event_id, participant.telegram_id):
        return
    if not await _check_outbound_rate(redis):
        logger.warning(
            "outbound Telegram rate limit hit — dropping FULFILLED_PARTICIPANT for telegram_id=%s",
            participant.telegram_id,
        )
        return

    t = _text(participant.language_code)
    text = (
        t["fulfilled_group_gift_body"]
        if event.get("source") == "group_gift"
        else t["fulfilled_booking_body"]
    )
    url = wish_url_by_id(
        mini_app_url,
        event["owner_user_id"],
        event["wishlist_id"],
        event["wish_id"],
    )
    try:
        await _send(bot, participant.telegram_id, text, t["open_wish"], url)
        logger.info(
            "sent FULFILLED_PARTICIPANT notification to telegram_id=%s", participant.telegram_id
        )
    except Exception:
        logger.exception(
            "failed to send FULFILLED_PARTICIPANT notification to telegram_id=%s",
            participant.telegram_id,
        )


async def _get_followers(db: AsyncSession, owner_id: UUID) -> list[tuple[int, str | None]]:
    """return (telegram_id, language_code) for all followers of owner"""
    result = await db.execute(
        select(User.telegram_id, User.language_code)
        .join(Follow, Follow.follower_user_id == User.id)
        .where(Follow.followed_user_id == owner_id)
    )
    return list(result.all())


async def handle_transfer_reported(
    event: dict,
    db: AsyncSession,
    bot: Bot,
    redis: Redis,
    mini_app_url: str,
) -> None:
    """notify organizer when a contributor reports a transfer, with confirm/reject buttons"""
    organizer_id = UUID(event["organizer_user_id"])
    event_id = event["event_id"]

    result = await db.execute(select(User).where(User.id == organizer_id))
    organizer = result.scalar_one_or_none()
    if organizer is None or organizer.telegram_id is None:
        return

    if await _is_duplicate(redis, event_id, organizer.telegram_id):
        return

    if not await _check_outbound_rate(redis):
        logger.warning(
            "outbound Telegram rate limit hit — dropping TRANSFER_REPORTED for telegram_id=%s",
            organizer.telegram_id,
        )
        return

    t = _text(organizer.language_code)
    text = t["gg_transfer_reported_body"].format(
        contributor=event["contributor_first_name"],
        amount=event["amount"],
        currency=event["currency"],
        wish_title=event["wish_title"],
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t["gg_confirm_btn"],
                    callback_data=f"gg_confirm:{event['contribution_id']}",
                ),
                InlineKeyboardButton(
                    text=t["gg_reject_btn"],
                    callback_data=f"gg_reject:{event['contribution_id']}",
                ),
            ]
        ]
    )
    try:
        await bot.send_message(chat_id=organizer.telegram_id, text=text, reply_markup=keyboard)
        logger.info("sent TRANSFER_REPORTED notification to telegram_id=%s", organizer.telegram_id)
    except Exception:
        logger.exception(
            "failed to send TRANSFER_REPORTED notification to telegram_id=%s", organizer.telegram_id
        )


async def handle_transfer_confirmed(
    event: dict,
    db: AsyncSession,
    bot: Bot,
    redis: Redis,
    mini_app_url: str,
) -> None:
    """notify contributor that their transfer was confirmed"""
    contributor_id = UUID(event["contributor_user_id"])
    event_id = event["event_id"]

    result = await db.execute(select(User).where(User.id == contributor_id))
    contributor = result.scalar_one_or_none()
    if contributor is None or contributor.telegram_id is None:
        return

    if await _is_duplicate(redis, event_id, contributor.telegram_id):
        return

    if not await _check_outbound_rate(redis):
        logger.warning(
            "outbound Telegram rate limit hit — dropping TRANSFER_CONFIRMED for telegram_id=%s",
            contributor.telegram_id,
        )
        return

    t = _text(contributor.language_code)
    text = t["gg_transfer_confirmed_body"].format(
        wish_title=event["wish_title"],
        percent=event["percent_complete"],
    )
    url = wish_url_by_id(
        mini_app_url,
        event["owner_user_id"],
        event["wishlist_id"],
        event["wish_id"],
    )
    try:
        await _send(bot, contributor.telegram_id, text, t["gg_open_gift"], url)
        logger.info(
            "sent TRANSFER_CONFIRMED notification to telegram_id=%s", contributor.telegram_id
        )
    except Exception:
        logger.exception(
            "failed to send TRANSFER_CONFIRMED notification to telegram_id=%s",
            contributor.telegram_id,
        )


async def handle_transfer_rejected(
    event: dict,
    db: AsyncSession,
    bot: Bot,
    redis: Redis,
    mini_app_url: str,
) -> None:
    """notify contributor that their reported transfer was rejected"""
    contributor_id = UUID(event["contributor_user_id"])
    event_id = event["event_id"]

    result = await db.execute(select(User).where(User.id == contributor_id))
    contributor = result.scalar_one_or_none()
    if contributor is None or contributor.telegram_id is None:
        return

    if await _is_duplicate(redis, event_id, contributor.telegram_id):
        return

    if not await _check_outbound_rate(redis):
        logger.warning(
            "outbound Telegram rate limit hit — dropping TRANSFER_REJECTED for telegram_id=%s",
            contributor.telegram_id,
        )
        return

    t = _text(contributor.language_code)
    text = t["gg_transfer_rejected_body"].format(wish_title=event["wish_title"])
    try:
        await bot.send_message(chat_id=contributor.telegram_id, text=text)
        logger.info(
            "sent TRANSFER_REJECTED notification to telegram_id=%s", contributor.telegram_id
        )
    except Exception:
        logger.exception(
            "failed to send TRANSFER_REJECTED notification to telegram_id=%s",
            contributor.telegram_id,
        )


async def handle_group_gift_completed(
    event: dict,
    db: AsyncSession,
    bot: Bot,
    redis: Redis,
    mini_app_url: str,
) -> None:
    """notify organizer and all contributors that the group gift goal has been reached.

    The wish owner is neither the organizer nor in the contributor list, so payment
    details are never sent to them by construction — no extra filtering needed.
    """
    organizer_id = UUID(event["organizer_user_id"])
    contributor_ids = [UUID(uid) for uid in event["contributor_user_ids"]]
    collection_type = event["collection_type"]
    wish_title = event["wish_title"]
    total_collected = event["total_collected"]
    currency = event["currency"]
    payment_method = event["payment_method"]
    payment_phone = event["payment_phone"]
    payment_comment = event.get("payment_comment", "")
    group_gift_id = event["group_gift_id"]

    result = await db.execute(select(User).where(User.id == organizer_id))
    organizer = result.scalar_one_or_none()

    contributors: list[User] = []
    if contributor_ids:
        result = await db.execute(select(User).where(User.id.in_(contributor_ids)))
        contributors = list(result.scalars().all())

    # organizer message
    if organizer and organizer.telegram_id is not None:
        dedup_key = f"notif:gg_complete:{group_gift_id}:{organizer.telegram_id}"
        already_sent = await redis.set(dedup_key, "1", nx=True, ex=DEDUP_TTL_SECONDS) is None
        if not already_sent:
            if not await _check_outbound_rate(redis):
                logger.warning(
                    "outbound rate limit hit — dropping GROUP_GIFT_COMPLETED (organizer) for telegram_id=%s",
                    organizer.telegram_id,
                )
            else:
                t = _text(organizer.language_code)
                if collection_type == "immediate":
                    body = t["gg_completed_organizer_immediate"].format(
                        wish_title=wish_title,
                        amount=total_collected,
                        currency=currency,
                    )
                else:
                    body = t["gg_completed_organizer_commit"].format(
                        wish_title=wish_title,
                        amount=total_collected,
                        currency=currency,
                        payment_method=payment_method,
                        payment_phone=payment_phone,
                    )
                    if payment_comment:
                        body += f"\n\n{payment_comment}"
                try:
                    await bot.send_message(chat_id=organizer.telegram_id, text=body)
                    logger.info(
                        "sent GROUP_GIFT_COMPLETED (organizer) to telegram_id=%s",
                        organizer.telegram_id,
                    )
                except Exception:
                    logger.exception(
                        "failed to send GROUP_GIFT_COMPLETED (organizer) to telegram_id=%s",
                        organizer.telegram_id,
                    )

    # contributor messages
    for contributor in contributors:
        if contributor.telegram_id is None:
            continue
        dedup_key = f"notif:gg_complete:{group_gift_id}:{contributor.telegram_id}"
        already_sent = await redis.set(dedup_key, "1", nx=True, ex=DEDUP_TTL_SECONDS) is None
        if already_sent:
            continue
        if not await _check_outbound_rate(redis):
            logger.warning(
                "outbound rate limit hit — dropping GROUP_GIFT_COMPLETED (contributor) for telegram_id=%s",
                contributor.telegram_id,
            )
            continue
        t = _text(contributor.language_code)
        if collection_type == "immediate":
            body = t["gg_completed_contributor_immediate"].format(wish_title=wish_title)
        else:
            body = t["gg_completed_contributor_commit"].format(
                wish_title=wish_title,
                payment_method=payment_method,
                payment_phone=payment_phone,
            )
            if payment_comment:
                body += f"\n\n{payment_comment}"
        try:
            await bot.send_message(chat_id=contributor.telegram_id, text=body)
            logger.info(
                "sent GROUP_GIFT_COMPLETED (contributor) to telegram_id=%s", contributor.telegram_id
            )
        except Exception:
            logger.exception(
                "failed to send GROUP_GIFT_COMPLETED (contributor) to telegram_id=%s",
                contributor.telegram_id,
            )


async def handle_group_gift_created(
    event: dict,
    db: AsyncSession,
    bot: Bot,
    redis: Redis,
    mini_app_url: str,
) -> None:
    """group gift start notifications are intentionally muted"""
    return

# telegram bot service
import asyncio
import logging

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestUsers,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from sqlalchemy import select
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.db.models import User
from app.db.session import async_session_factory, dispose_db
from app.integrations.redis import close_redis, get_redis_client
from app.modules.notifications.worker import run_notification_worker
from app.modules.users.discovery import create_discovery_token

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
FIND_FRIENDS_REQUEST_ID = 1
FIND_FRIENDS_RATE_LIMIT = 10
FIND_FRIENDS_RATE_WINDOW_SECONDS = 60
CONFETTI_MESSAGE_EFFECT_ID = "5046509860389126442"
BOT_TEXT = {
    "en": {
        "find_friends": "Find friends",
        "open_wished": "Open Wished",
        "welcome": (
            "Welcome to Wished!\n\n"
            "Create, share, and track your wishlists.\n\n"
            "Choose an option below to continue."
        ),
        "open_profile": "Open {name}",
        "registered": "{name} is registered in Wished.",
        "not_available": "{name} is not available in Wished.",
        "not_registered": "{name} has not joined Wished yet.",
        "invite": "Invite to Wished",
        "rate_limited": "Too many requests. Please try again in a minute.",
        "unknown_user": "This user",
    },
    "ru": {
        "find_friends": "Найти друзей",
        "open_wished": "Открыть Wished",
        "welcome": (
            "Добро пожаловать в Wished!\n\n"
            "Создавайте, делитесь и отслеживайте списки желаний.\n\n"
            "Выберите действие ниже, чтобы продолжить."
        ),
        "open_profile": "Открыть {name}",
        "registered": "{name} зарегистрирован в Wished.",
        "not_available": "{name} недоступен в Wished.",
        "not_registered": "{name} ещё не присоединился к Wished.",
        "invite": "Пригласить в Wished",
        "rate_limited": "Слишком много запросов. Повторите через минуту.",
        "unknown_user": "Этот пользователь",
    },
    "kz": {
        "find_friends": "Достарды табу",
        "open_wished": "Wished ашу",
        "welcome": (
            "Wished қолданбасына қош келдіңіз!\n\n"
            "Тілектер тізімін жасап, бөлісіп, бақылаңыз.\n\n"
            "Жалғастыру үшін төмендегі әрекетті таңдаңыз."
        ),
        "open_profile": "{name} профилін ашу",
        "registered": "{name} Wished жүйесінде тіркелген.",
        "not_available": "{name} Wished жүйесінде қолжетімсіз.",
        "not_registered": "{name} Wished жүйесіне әлі қосылмаған.",
        "invite": "Wished жүйесіне шақыру",
        "rate_limited": "Сұраулар тым көп. Бір минуттан кейін қайталап көріңіз.",
        "unknown_user": "Бұл пайдаланушы",
    },
}
INVITE_TEXT = (
    "Join me on Wished. "
    "Create wishlists, reserve gifts, and share ideas with friends."
)


async def start_handler(message: types.Message) -> None:
    """handle start command"""
    settings = get_settings()
    text = _bot_text(message)
    await message.answer(
        text["welcome"],
        reply_markup=_friend_discovery_keyboard(text, settings.telegram_mini_app_url),
    )


async def find_handler(message: types.Message) -> None:
    """show native user picker"""
    settings = get_settings()
    text = _bot_text(message)
    await message.answer(
        text["find_friends"],
        reply_markup=_friend_discovery_keyboard(text, settings.telegram_mini_app_url),
    )


def _friend_discovery_keyboard(text: dict[str, str], web_app_url: str | None) -> ReplyKeyboardMarkup:
    """build discovery keyboard"""
    app_url = web_app_url or "http://localhost:3000"
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=text["open_wished"],
                    web_app=WebAppInfo(url=app_url),
                )
            ],
            [
                KeyboardButton(
                    text=text["find_friends"],
                    request_users=KeyboardButtonRequestUsers(
                        request_id=FIND_FRIENDS_REQUEST_ID,
                        user_is_bot=False,
                        max_quantity=10,
                        request_name=True,
                        request_username=True,
                        request_photo=True,
                    ),
                )
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
        input_field_placeholder=text["find_friends"],
    )


async def users_shared_handler(message: types.Message) -> None:
    """handle selected telegram users"""
    if not message.users_shared or message.users_shared.request_id != FIND_FRIENDS_REQUEST_ID:
        return
    if not message.from_user:
        return

    text = _bot_text(message)
    if not await _allow_find_request(message.from_user.id):
        await message.answer(text["rate_limited"])
        return

    selected_users = message.users_shared.users
    shared_users = [
        shared_user
        for shared_user in selected_users
        if shared_user.user_id != message.from_user.id
    ]
    if not shared_users:
        await _delete_shared_users_message(message)
        return

    telegram_ids = [shared_user.user_id for shared_user in shared_users]
    async with async_session_factory() as db:
        result = await db.execute(
            select(User).where(
                User.telegram_id.in_(telegram_ids),
                User.telegram_id != message.from_user.id,
            )
        )
        registered_users = {
            user.telegram_id: user
            for user in result.scalars().all()
        }

        settings = get_settings()
        for shared_user in shared_users:
            user = registered_users.get(shared_user.user_id)
            display_name = _shared_user_name(shared_user, text["unknown_user"])
            if user and user.username:
                discovery_token = await create_discovery_token(
                    get_redis_client(),
                    message.from_user.id,
                    user.telegram_id,
                    db=db,
                )
                web_app_url = settings.telegram_mini_app_url or "http://localhost:3000"
                profile_url = (
                    f"{web_app_url}/users"
                    f"?profile={user.username}"
                    f"&profile_token={discovery_token}"
                )
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=text["open_profile"].format(name=display_name),
                                web_app=WebAppInfo(url=profile_url),
                            )
                        ]
                    ]
                )
                await message.answer(
                    text["registered"].format(name=display_name),
                    reply_markup=keyboard,
                    message_effect_id=CONFETTI_MESSAGE_EFFECT_ID,
                )
                continue

            if user:
                await message.answer(text["not_available"].format(name=display_name))
                continue

            bot_url = f"https://t.me/{settings.telegram_bot_username}"
            invite_message = f"{INVITE_TEXT}"
            invite_url = f"https://t.me/share/url?url={_urlencode(bot_url)}&text={_urlencode(invite_message)}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=text["invite"],
                            url=invite_url,
                        )
                    ]
                ]
            )
            await message.answer(
                text["not_registered"].format(name=display_name),
                reply_markup=keyboard,
            )


def _shared_user_name(shared_user: types.SharedUser, fallback: str) -> str:
    """build shared user name"""
    full_name = " ".join(
        part
        for part in [shared_user.first_name, shared_user.last_name]
        if part
    )
    if full_name:
        return full_name
    if shared_user.username:
        return f"@{shared_user.username}"
    return fallback


async def _delete_shared_users_message(message: types.Message) -> None:
    """delete shared message"""
    try:
        await message.delete()
    except Exception:
        logger.debug("shared users message could not be deleted")


def _bot_text(message: types.Message) -> dict[str, str]:
    """get localized bot text"""
    language_code = message.from_user.language_code if message.from_user else "en"
    language = "kz" if language_code in {"kk", "kz"} else language_code
    return BOT_TEXT.get(language, BOT_TEXT["en"])


async def _allow_find_request(telegram_id: int) -> bool:
    """rate limit friend discovery"""
    try:
        redis = get_redis_client()
        key = f"rate:find-friends:{telegram_id}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, FIND_FRIENDS_RATE_WINDOW_SECONDS)
        return count <= FIND_FRIENDS_RATE_LIMIT
    except RedisError:
        logger.exception("friend discovery rate limit failed")
        return False


def _urlencode(value: str) -> str:
    """encode telegram share text"""
    from urllib.parse import quote

    return quote(value, safe="")


async def main() -> None:
    """start telegram bot polling"""
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.error("telegram bot token not set")
        return

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.message.register(start_handler, CommandStart())
    dp.message.register(find_handler, Command("find"))
    dp.message.register(users_shared_handler, F.users_shared)

    web_app_url = settings.telegram_mini_app_url or "http://localhost:3000"
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Open Wished",
            web_app=WebAppInfo(url=web_app_url),
        )
    )

    # blpop blocks for up to BLPOP_TIMEOUT seconds — the client must not have
    # a socket timeout shorter than that, so we use a dedicated connection here
    from redis.asyncio import Redis as AsyncRedis
    blocking_redis = AsyncRedis.from_url(
        settings.redis_connection_url,
        encoding="utf-8",
        decode_responses=True,
        socket_timeout=None,
    )
    redis = get_redis_client()
    notification_task = asyncio.create_task(
        run_notification_worker(blocking_redis, bot, async_session_factory, web_app_url)
    )

    logger.info("starting telegram bot polling")
    try:
        await dp.start_polling(bot)
    finally:
        notification_task.cancel()
        try:
            await notification_task
        except asyncio.CancelledError:
            pass
        await blocking_redis.aclose()
        await dispose_db()
        await close_redis()


if __name__ == "__main__":
    asyncio.run(main())

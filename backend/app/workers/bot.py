# telegram bot service
import asyncio
import html
import logging
from uuid import UUID, uuid4

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
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
from app.db.models.group_gifts import GroupGift, GroupGiftContribution
from app.db.models.wishlists import Wishlist
from app.db.session import async_session_factory, dispose_db
from app.integrations.redis import close_redis, get_redis_client
from app.integrations.telegram.start_param import decode_wishlist_start_param
from app.modules.group_gifts import service as group_gift_service
from app.modules.notifications.worker import run_notification_worker
from app.modules.users.discovery import create_discovery_token
from app.modules.wishlists.share_token import validate_wishlist_share_token

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
FIND_FRIENDS_REQUEST_ID = 1
FIND_FRIENDS_RATE_LIMIT = 10
FIND_FRIENDS_RATE_WINDOW_SECONDS = 60
CONFETTI_MESSAGE_EFFECT_ID = "5046509860389126442"
LANG_PREF_KEY = "bot:lang_pref:{telegram_id}"
LANG_PREF_TTL = 30 * 24 * 3600

BOT_TEXT = {
    "en": {
        "find_friends": "Find friends",
        "open_wished": "Open Wished",
        "welcome": (
            "Welcome to Wished. "
            "Create wishlists, discover wishes, and coordinate gifts with friends. "
            "Choose an option below to continue. "
            "Press Open Wished to get started and Find friends to connect with people you know."
        ),
        "open_profile": "Open {name}",
        "registered": "{name} is registered in Wished.",
        "not_available": "{name} is not available in Wished.",
        "not_registered": "{name} has not joined Wished yet.",
        "invite": "Invite to Wished",
        "invite_text": "Join me on Wished. Create wishlists, reserve gifts, and share ideas with friends.",
        "rate_limited": "Too many requests. Please try again in a minute.",
        "unknown_user": "This user",
        "language_changed": "Language set to English.",
        "language_select": "Please choose your language.",
        "share_wishlist_prefix": "Here, see my wishlist in Wished:",
        "share_wishlist_result": "Share wishlist",
    },
    "ru": {
        "find_friends": "Найти друзей",
        "open_wished": "Открыть Wished",
        "welcome": (
            "Добро пожаловать в Wished. "
            "Создавайте вишлисты, находите желания друзей и удобно координируйте подарки. "
            "Выберите действие ниже, чтобы продолжить. "
            "Нажмите «Открыть Wished», чтобы начать, и «Найти друзей», чтобы связаться с людьми, которых вы знаете."
        ),
        "open_profile": "Открыть {name}",
        "registered": "{name} зарегистрирован в Wished.",
        "not_available": "{name} недоступен в Wished.",
        "not_registered": "{name} ещё не присоединился к Wished.",
        "invite": "Пригласить в Wished",
        "invite_text": "Присоединяйся ко мне в Wished. Создавай вишлисты, резервируй подарки и делись идеями с друзьями.",
        "rate_limited": "Слишком много запросов. Повторите через минуту.",
        "unknown_user": "Этот пользователь",
        "language_changed": "Язык изменён на русский.",
        "language_select": "Пожалуйста, выберите язык.",
        "share_wishlist_prefix": "Смотри мой список желаний в Wished:",
        "share_wishlist_result": "Поделиться вишлистом",
    },
    "kz": {
        "find_friends": "Достарды табу",
        "open_wished": "Wished ашу",
        "welcome": (
            "Wished қолданбасына қош келдіңіз. "
            "Тілектер тізімін жасап, достарыңыздың тілектерін қарап, сыйлықтарды бірге жоспарлаңыз. "
            "Жалғастыру үшін төмендегі әрекетті таңдаңыз. "
            "Бастау үшін «Wished ашу» және таныстарыңызбен байланысу үшін «Достарды табу» батырмасын басыңыз."
        ),
        "open_profile": "{name} профилін ашу",
        "registered": "{name} Wished жүйесінде тіркелген.",
        "not_available": "{name} Wished жүйесінде қолжетімсіз.",
        "not_registered": "{name} Wished жүйесіне әлі қосылмаған.",
        "invite": "Wished жүйесіне шақыру",
        "invite_text": "Маған Wished жүйесінде қосыл. Тілектер тізімін жасап, сыйлықтарды брондап, достарыңмен идеялар бөліс.",
        "rate_limited": "Сұраулар тым көп. Бір минуттан кейін қайталап көріңіз.",
        "unknown_user": "Бұл пайдаланушы",
        "language_changed": "Тіл қазақша деп орнатылды.",
        "language_select": "Тіліңізді таңдаңыз.",
        "share_wishlist_prefix": "Wished-тегі тілектер тізімімді қара:",
        "share_wishlist_result": "Тілектер тізімімен бөлісу",
    },
}

LANGUAGE_SELECT_MSG = (
    "English — Please choose your language.\n"
    "Қазақша — Тіліңізді таңдаңыз.\n"
    "Русский — Пожалуйста, выберите язык."
)

LANG_BUTTON_LABELS: dict[str, str] = {
    "English": "en",
    "Қазақша": "kz",
    "Русский": "ru",
}


def _language_keyboard() -> ReplyKeyboardMarkup:
    """reply keyboard for language selection"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="English")],
            [KeyboardButton(text="Қазақша")],
            [KeyboardButton(text="Русский")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def _get_user_lang(telegram_id: int) -> str:
    """get language preference from redis cache then db; default en"""
    try:
        redis = get_redis_client()
        cached = await redis.get(LANG_PREF_KEY.format(telegram_id=telegram_id))
        if cached and cached in BOT_TEXT:
            return cached
    except Exception:
        logger.debug("redis lang lookup failed for telegram_id=%s", telegram_id)

    try:
        async with async_session_factory() as db:
            result = await db.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            if user and user.language_code:
                lang = "kz" if user.language_code in {"kk", "kz"} else user.language_code
                if lang in BOT_TEXT:
                    return lang
    except Exception:
        logger.debug("db lang lookup failed for telegram_id=%s", telegram_id)

    return "en"


async def _has_language_preference(telegram_id: int) -> bool:
    """return True only if user explicitly chose a language via the bot"""
    try:
        redis = get_redis_client()
        cached = await redis.get(LANG_PREF_KEY.format(telegram_id=telegram_id))
        if cached and cached in BOT_TEXT:
            return True
    except Exception:
        pass
    return False


async def _save_language_preference(telegram_id: int, lang: str) -> None:
    """persist language choice to redis and db"""
    try:
        redis = get_redis_client()
        await redis.set(LANG_PREF_KEY.format(telegram_id=telegram_id), lang, ex=LANG_PREF_TTL)
    except Exception:
        logger.exception("failed to cache language preference for telegram_id=%s", telegram_id)

    try:
        async with async_session_factory() as db:
            result = await db.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            if user:
                user.language_code = lang
                await db.commit()
    except Exception:
        logger.exception("failed to save language preference to db for telegram_id=%s", telegram_id)


async def _bot_text(message: types.Message) -> dict[str, str]:
    """get localized bot text from stored preference"""
    if not message.from_user:
        return BOT_TEXT["en"]
    lang = await _get_user_lang(message.from_user.id)
    return BOT_TEXT[lang]


async def start_handler(message: types.Message) -> None:
    """handle start command — always show language selector first"""
    if not message.from_user:
        return
    await message.answer(
        "Please choose your language. Тіліңізді таңдаңыз. Пожалуйста, выберите язык.",
        reply_markup=_language_keyboard(),
    )


async def language_text_handler(message: types.Message) -> None:
    """handle language button tap from reply keyboard"""
    if not message.from_user or not message.text:
        return

    lang = LANG_BUTTON_LABELS.get(message.text, "en")
    await _save_language_preference(message.from_user.id, lang)

    settings = get_settings()
    text = BOT_TEXT[lang]
    await message.answer(
        text["welcome"],
        reply_markup=_friend_discovery_keyboard(text, settings.telegram_mini_app_url),
    )


async def language_command_handler(message: types.Message) -> None:
    """handle /language command — show language selector"""
    await message.answer(
        "Please choose your language. Тіліңізді таңдаңыз. Пожалуйста, выберите язык.",
        reply_markup=_language_keyboard(),
    )


async def find_handler(message: types.Message) -> None:
    """show native user picker"""
    settings = get_settings()
    text = await _bot_text(message)
    await message.answer(
        text["find_friends"],
        reply_markup=_friend_discovery_keyboard(text, settings.telegram_mini_app_url),
    )


def _friend_discovery_keyboard(
    text: dict[str, str], web_app_url: str | None
) -> ReplyKeyboardMarkup:
    """build discovery keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[
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

    text = await _bot_text(message)
    if not await _allow_find_request(message.from_user.id):
        await message.answer(text["rate_limited"])
        return

    selected_users = message.users_shared.users
    shared_users = [
        shared_user for shared_user in selected_users if shared_user.user_id != message.from_user.id
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
        registered_users = {user.telegram_id: user for user in result.scalars().all()}

        settings = get_settings()
        for shared_user in shared_users:
            user = registered_users.get(shared_user.user_id)
            display_name = _shared_user_name(shared_user, text["unknown_user"])
            if user:
                discovery_token = await create_discovery_token(
                    get_redis_client(),
                    message.from_user.id,
                    user.telegram_id,
                    db=db,
                )
                web_app_url = settings.telegram_mini_app_url or "http://localhost:3000"
                profile_url = (
                    f"{web_app_url}/users?profile_id={user.id}&profile_token={discovery_token}"
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

            bot_url = f"https://t.me/{settings.telegram_bot_username}"
            invite_url = f"https://t.me/share/url?url={_urlencode(bot_url)}&text={_urlencode(text['invite_text'])}"
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
    full_name = " ".join(part for part in [shared_user.first_name, shared_user.last_name] if part)
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


async def gg_confirm_handler(callback: types.CallbackQuery) -> None:
    """confirm a reported group gift transfer"""
    if not callback.data or not callback.from_user:
        await callback.answer()
        return

    contribution_id_str = callback.data.split(":", 1)[1]

    try:
        contribution_id = UUID(contribution_id_str)
    except ValueError:
        await callback.answer("Invalid request", show_alert=True)
        return

    async with async_session_factory() as db:
        result = await db.execute(
            select(GroupGiftContribution).where(GroupGiftContribution.id == contribution_id)
        )
        contribution = result.scalar_one_or_none()
        if contribution is None:
            await callback.answer("Not found", show_alert=True)
            return

        result = await db.execute(
            select(GroupGift).where(GroupGift.id == contribution.group_gift_id)
        )
        gift = result.scalar_one_or_none()

        result = await db.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if user is None:
            await callback.answer("Not authorized", show_alert=True)
            return

        if gift is None or user.id != gift.organizer_user_id:
            await callback.answer("Not authorized", show_alert=True)
            return

        if contribution.status != "waiting_confirmation":
            await callback.answer("Already actioned", show_alert=True)
            return

        try:
            redis = get_redis_client()
            await group_gift_service.confirm_transfer(
                db, user, contribution.id, confirmed=True, redis=redis
            )
        except Exception:
            logger.exception(
                "gg_confirm_handler: confirm_transfer failed for contribution_id=%s",
                contribution_id,
            )
            await callback.answer("Something went wrong", show_alert=True)
            return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass  # message may be too old to edit — not fatal

    await callback.answer()


async def gg_reject_handler(callback: types.CallbackQuery) -> None:
    """reject a reported group gift transfer"""
    if not callback.data or not callback.from_user:
        await callback.answer()
        return

    contribution_id_str = callback.data.split(":", 1)[1]

    try:
        contribution_id = UUID(contribution_id_str)
    except ValueError:
        await callback.answer("Invalid request", show_alert=True)
        return

    async with async_session_factory() as db:
        result = await db.execute(
            select(GroupGiftContribution).where(GroupGiftContribution.id == contribution_id)
        )
        contribution = result.scalar_one_or_none()
        if contribution is None:
            await callback.answer("Not found", show_alert=True)
            return

        result = await db.execute(
            select(GroupGift).where(GroupGift.id == contribution.group_gift_id)
        )
        gift = result.scalar_one_or_none()

        result = await db.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if user is None:
            await callback.answer("Not authorized", show_alert=True)
            return

        if gift is None or user.id != gift.organizer_user_id:
            await callback.answer("Not authorized", show_alert=True)
            return

        if contribution.status != "waiting_confirmation":
            await callback.answer("Already actioned", show_alert=True)
            return

        try:
            redis = get_redis_client()
            await group_gift_service.confirm_transfer(
                db, user, contribution.id, confirmed=False, redis=redis
            )
        except Exception:
            logger.exception(
                "gg_reject_handler: confirm_transfer failed for contribution_id=%s", contribution_id
            )
            await callback.answer("Something went wrong", show_alert=True)
            return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass  # message may be too old to edit — not fatal

    await callback.answer()


INLINE_QUERY_CACHE_TIME = 30


def _build_wishlist_share_message(start_param: str, title: str, prefix: str) -> str:
    """build the HTML inline message: localized prefix + wishlist name as a hidden deep link"""
    settings = get_settings()
    bot_username = settings.telegram_bot_username or "wished_app_bot"
    # start_param is base64url + url-safe token, so it needs no further encoding
    deep_link = f"https://t.me/{bot_username}/wished?startapp={start_param}"
    safe_title = html.escape(title) or "Wished"
    # the deep link lives only in the href so Telegram still renders the Mini App
    # preview card while the raw URL never appears in the visible message body
    return f'{html.escape(prefix)}\n<a href="{html.escape(deep_link, quote=True)}">{safe_title}</a>'


async def inline_query_handler(inline_query: types.InlineQuery) -> None:
    """serve a clean shareable wishlist message via Telegram inline mode"""
    if not inline_query.from_user:
        await inline_query.answer([], cache_time=INLINE_QUERY_CACHE_TIME, is_personal=True)
        return

    text = BOT_TEXT[await _get_user_lang(inline_query.from_user.id)]

    # the query is "<start_param> <title>"; we only trust the start param and load
    # the authoritative title from the database — never the inline-supplied title
    start_param = inline_query.query.strip().split(" ", 1)[0]
    decoded = decode_wishlist_start_param(start_param)
    if decoded is None:
        await inline_query.answer([], cache_time=INLINE_QUERY_CACHE_TIME, is_personal=True)
        return

    async with async_session_factory() as db:
        result = await db.execute(select(Wishlist).where(Wishlist.id == decoded.wishlist_id))
        wishlist = result.scalar_one_or_none()

    # reject missing wishlists, and private ones without a valid share token
    if wishlist is None:
        await inline_query.answer([], cache_time=INLINE_QUERY_CACHE_TIME, is_personal=True)
        return
    if wishlist.visibility != "public":
        valid = await validate_wishlist_share_token(
            get_redis_client(), decoded.share_token, decoded.wishlist_id
        )
        if not valid:
            await inline_query.answer([], cache_time=INLINE_QUERY_CACHE_TIME, is_personal=True)
            return

    message_text = _build_wishlist_share_message(
        start_param, wishlist.title, text["share_wishlist_prefix"]
    )
    article = InlineQueryResultArticle(
        id=uuid4().hex,
        title=text["share_wishlist_result"],
        description=wishlist.title,
        input_message_content=InputTextMessageContent(
            message_text=message_text,
            parse_mode="HTML",
        ),
    )
    await inline_query.answer([article], cache_time=INLINE_QUERY_CACHE_TIME, is_personal=True)


async def main() -> None:
    """start telegram bot polling"""
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.error("telegram bot token not set")
        return

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.message.register(start_handler, CommandStart())
    dp.message.register(language_command_handler, Command("language"))
    dp.message.register(find_handler, Command("find"))
    dp.message.register(users_shared_handler, F.users_shared)
    dp.message.register(language_text_handler, F.text.in_(LANG_BUTTON_LABELS.keys()))
    dp.callback_query.register(gg_confirm_handler, F.data.startswith("gg_confirm:"))
    dp.callback_query.register(gg_reject_handler, F.data.startswith("gg_reject:"))
    dp.inline_query.register(inline_query_handler)

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

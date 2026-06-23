"""telegram bot tests"""
from types import SimpleNamespace

import pytest
from aiogram.types import SharedUser, UsersShared

from app.workers import bot


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _allow_request(telegram_id: int) -> bool:
    return True


async def _create_discovery_token(redis, requester_telegram_id: int, target_telegram_id: int, db=None) -> str:
    return "test-token"


class FakeMessage:
    """fake telegram message"""

    def __init__(self, users_shared=None) -> None:
        self.users_shared = users_shared
        self.from_user = SimpleNamespace(id=999, language_code="en")
        self.answers = []
        self.deleted = False

    async def answer(self, text, reply_markup=None, **kwargs) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup, **kwargs})

    async def delete(self) -> None:
        self.deleted = True




class FakeSession:
    """fake database session"""

    def __init__(self, user=None) -> None:
        self.user = user
        self._committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass

    async def execute(self, statement):
        return FakeResult(self.user)

    async def commit(self) -> None:
        self._committed = True


class FakeResult:
    """fake query result"""

    def __init__(self, user) -> None:
        self.user = user

    def scalars(self):
        return self

    def all(self):
        return [self.user] if self.user else []

    def scalar_one_or_none(self):
        return self.user


class FakeRedis:
    """fake redis client"""

    def __init__(self, stored: dict | None = None) -> None:
        self._store = stored if stored is not None else {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value, ex=None) -> None:
        self._store[key] = value


# ---------------------------------------------------------------------------
# /start — new user (no language set)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_handler_shows_language_selector_for_new_user(monkeypatch) -> None:
    """new user without language preference sees language selection"""
    message = FakeMessage()
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=None))

    await bot.start_handler(message)

    assert len(message.answers) == 1
    assert "Please choose your language" in message.answers[0]["text"]
    keyboard = message.answers[0]["reply_markup"]
    labels = [row[0].text for row in keyboard.keyboard]
    assert labels == ["English", "Қазақша", "Русский"]


@pytest.mark.asyncio
async def test_start_handler_always_shows_language_selector(monkeypatch) -> None:
    """start_handler shows language selector regardless of existing preference"""
    message = FakeMessage()
    user = SimpleNamespace(telegram_id=999, language_code="en")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis({"bot:lang_pref:999": "en"}))
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=user))

    await bot.start_handler(message)

    assert len(message.answers) == 1
    assert "Please choose your language" in message.answers[0]["text"]
    keyboard = message.answers[0]["reply_markup"]
    labels = [row[0].text for row in keyboard.keyboard]
    assert labels == ["English", "Қазақша", "Русский"]


@pytest.mark.asyncio
async def test_language_text_handler_shows_english_welcome(monkeypatch) -> None:
    """language_text_handler shows English welcome after tapping English"""
    message = _lang_message("English")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=SimpleNamespace(telegram_id=999, language_code=None)))
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.language_text_handler(message)

    assert len(message.answers) == 1
    assert message.answers[0]["text"].startswith("Welcome to Wished.")


@pytest.mark.asyncio
async def test_language_text_handler_shows_russian_welcome(monkeypatch) -> None:
    """language_text_handler shows Russian welcome after tapping Русский"""
    message = _lang_message("Русский")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=SimpleNamespace(telegram_id=999, language_code=None)))
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.language_text_handler(message)

    assert "Добро пожаловать" in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_language_text_handler_shows_kazakh_welcome(monkeypatch) -> None:
    """language_text_handler shows Kazakh welcome after tapping Қазақша"""
    message = _lang_message("Қазақша")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=SimpleNamespace(telegram_id=999, language_code=None)))
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.language_text_handler(message)

    assert "қош келдіңіз" in message.answers[0]["text"]


# ---------------------------------------------------------------------------
# language selection via reply keyboard
# ---------------------------------------------------------------------------


def _lang_message(text: str, telegram_id: int = 999) -> FakeMessage:
    msg = FakeMessage()
    msg.from_user = SimpleNamespace(id=telegram_id, language_code="en")
    msg.text = text
    return msg


@pytest.mark.asyncio
async def test_language_text_handler_sets_english(monkeypatch) -> None:
    """tapping English saves en preference and shows English welcome"""
    redis_store = {}
    session = FakeSession(user=SimpleNamespace(telegram_id=999, language_code=None))
    message = _lang_message("English")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis(redis_store))
    monkeypatch.setattr(bot, "async_session_factory", lambda: session)
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.language_text_handler(message)

    assert redis_store.get("bot:lang_pref:999") == "en"
    assert session.user.language_code == "en"
    assert "Welcome to Wished." in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_language_text_handler_sets_kazakh(monkeypatch) -> None:
    """tapping Қазақша saves kz preference and shows Kazakh welcome"""
    redis_store = {}
    session = FakeSession(user=SimpleNamespace(telegram_id=999, language_code=None))
    message = _lang_message("Қазақша")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis(redis_store))
    monkeypatch.setattr(bot, "async_session_factory", lambda: session)
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.language_text_handler(message)

    assert redis_store.get("bot:lang_pref:999") == "kz"
    assert session.user.language_code == "kz"
    assert "қош келдіңіз" in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_language_text_handler_sets_russian(monkeypatch) -> None:
    """tapping Русский saves ru preference and shows Russian welcome"""
    redis_store = {}
    session = FakeSession(user=SimpleNamespace(telegram_id=999, language_code=None))
    message = _lang_message("Русский")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis(redis_store))
    monkeypatch.setattr(bot, "async_session_factory", lambda: session)
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.language_text_handler(message)

    assert redis_store.get("bot:lang_pref:999") == "ru"
    assert "Добро пожаловать" in message.answers[0]["text"]


# ---------------------------------------------------------------------------
# language persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_language_persists_across_sessions_via_redis(monkeypatch) -> None:
    """redis cache is checked first for language preference"""
    redis_store = {"bot:lang_pref:999": "ru"}
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis(redis_store))

    lang = await bot._get_user_lang(999)

    assert lang == "ru"


@pytest.mark.asyncio
async def test_language_falls_back_to_db_when_no_redis(monkeypatch) -> None:
    """db language is used when redis has no entry"""
    user = SimpleNamespace(telegram_id=999, language_code="kz")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=user))

    lang = await bot._get_user_lang(999)

    assert lang == "kz"


@pytest.mark.asyncio
async def test_language_defaults_to_en_when_no_preference(monkeypatch) -> None:
    """fallback to English when neither redis nor db has a language"""
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=None))

    lang = await bot._get_user_lang(999)

    assert lang == "en"


@pytest.mark.asyncio
async def test_language_kk_code_normalised_to_kz(monkeypatch) -> None:
    """Telegram language code kk is treated as kz"""
    user = SimpleNamespace(telegram_id=999, language_code="kk")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=user))

    lang = await bot._get_user_lang(999)

    assert lang == "kz"


# ---------------------------------------------------------------------------
# language switching (/language command)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_language_command_shows_selector(monkeypatch) -> None:
    """/language command shows the language selector regardless of current preference"""
    message = FakeMessage()

    await bot.language_command_handler(message)

    assert len(message.answers) == 1
    assert "Please choose your language" in message.answers[0]["text"]
    labels = [row[0].text for row in message.answers[0]["reply_markup"].keyboard]
    assert labels == ["English", "Қазақша", "Русский"]


@pytest.mark.asyncio
async def test_language_switching_updates_preference(monkeypatch) -> None:
    """switching language from en to ru updates both redis and db"""
    redis_store = {"bot:lang_pref:999": "en"}
    session = FakeSession(user=SimpleNamespace(telegram_id=999, language_code="en"))
    message = _lang_message("Русский")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis(redis_store))
    monkeypatch.setattr(bot, "async_session_factory", lambda: session)
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.language_text_handler(message)

    assert redis_store.get("bot:lang_pref:999") == "ru"
    assert session.user.language_code == "ru"


# ---------------------------------------------------------------------------
# find and users_shared handlers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_handler_sends_user_picker(monkeypatch) -> None:
    """find command shows native user picker keyboard"""
    message = FakeMessage()
    user = SimpleNamespace(telegram_id=999, language_code="en")
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=user))
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.find_handler(message)

    markup = message.answers[0]["reply_markup"]
    request = markup.keyboard[0][0].request_users
    assert request.request_id == bot.FIND_FRIENDS_REQUEST_ID
    assert request.user_is_bot is False
    assert request.max_quantity == 10


@pytest.mark.asyncio
async def test_users_shared_handler_matches_selected_users(monkeypatch) -> None:
    """selected registered user gets a profile link"""
    shared_user = SharedUser(
        user_id=123,
        first_name="Alice",
        username="alice",
    )
    message = FakeMessage(
        users_shared=UsersShared(
            request_id=bot.FIND_FRIENDS_REQUEST_ID,
            users=[shared_user],
        )
    )
    registered_user = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        telegram_id=123,
        username="alice",
        profile_visibility="public",
    )

    class MultiSession:
        """returns lang-lookup result first, then registered user list"""
        call_count = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def execute(self, statement):
            MultiSession.call_count += 1
            if MultiSession.call_count == 1:
                # _get_user_lang: no user in db
                return FakeResult(None)
            # users_shared_handler bulk lookup
            return FakeResult(registered_user)

    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(bot, "async_session_factory", lambda: MultiSession())
    monkeypatch.setattr(bot, "_allow_find_request", _allow_request)
    monkeypatch.setattr(bot, "create_discovery_token", _create_discovery_token)
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.users_shared_handler(message)

    assert message.answers[0]["text"] == "Alice is registered in Wished."
    assert message.answers[0]["message_effect_id"] == "5046509860389126442"
    assert message.deleted is False
    button = message.answers[0]["reply_markup"].inline_keyboard[0][0]
    assert button.web_app.url == "https://example.com/users?profile_id=00000000-0000-0000-0000-000000000001&profile_token=test-token"


@pytest.mark.asyncio
async def test_users_shared_handler_ignores_current_user(monkeypatch) -> None:
    """self selection is silently ignored and message deleted"""
    message = FakeMessage(
        users_shared=UsersShared(
            request_id=bot.FIND_FRIENDS_REQUEST_ID,
            users=[SharedUser(user_id=999, first_name="Current")],
        )
    )
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=None))
    monkeypatch.setattr(bot, "_allow_find_request", _allow_request)

    await bot.users_shared_handler(message)

    assert message.answers == []
    assert message.deleted is True


# ---------------------------------------------------------------------------
# fallback safety
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_handler_unknown_language_shows_selector(monkeypatch) -> None:
    """unknown language code in redis is not a valid preference — show selector"""
    message = FakeMessage()
    monkeypatch.setattr(bot, "get_redis_client", lambda: FakeRedis({"bot:lang_pref:999": "fr"}))
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(user=None))

    await bot.start_handler(message)

    assert "Please choose your language" in message.answers[0]["text"]

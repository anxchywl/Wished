"""telegram bot tests"""
from types import SimpleNamespace

import pytest
from aiogram.types import SharedUser, UsersShared

from app.workers import bot


@pytest.mark.asyncio
async def test_start_handler_sends_welcome(monkeypatch) -> None:
    """test start welcome"""
    message = FakeMessage()
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_things_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.start_handler(message)

    assert message.answers[0]["text"].startswith("Welcome to Wished!")
    markup = message.answers[0]["reply_markup"]
    assert markup.keyboard[0][0].text == "Open Wished"
    assert markup.keyboard[0][0].web_app.url == "https://example.com"
    assert markup.keyboard[1][0].text == "Find friends"
    assert markup.one_time_keyboard is False
    assert markup.is_persistent is True


@pytest.mark.asyncio
async def test_start_handler_sends_user_picker(monkeypatch) -> None:
    """test native user picker"""
    message = FakeMessage()
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_things_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.find_handler(message)

    markup = message.answers[0]["reply_markup"]
    assert markup.keyboard[0][0].web_app.url == "https://example.com"
    request = markup.keyboard[1][0].request_users
    assert request.request_id == bot.FIND_FRIENDS_REQUEST_ID
    assert request.user_is_bot is False
    assert request.max_quantity == 10
    assert request.request_name is True
    assert request.request_username is True
    assert request.request_photo is True


@pytest.mark.asyncio
async def test_users_shared_handler_matches_selected_users(monkeypatch) -> None:
    """test selected user matching"""
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
        telegram_id=123,
        username="alice",
        profile_visibility="public",
    )
    monkeypatch.setattr(bot, "async_session_factory", lambda: FakeSession(registered_user))
    monkeypatch.setattr(bot, "_allow_find_request", _allow_request)
    monkeypatch.setattr(bot, "create_discovery_token", _create_discovery_token)
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_username="wished_things_bot",
            telegram_mini_app_url="https://example.com",
        ),
    )

    await bot.users_shared_handler(message)

    assert message.answers[0]["text"] == "Alice is registered in Wished."
    assert message.answers[0]["message_effect_id"] == "5046509860389126442"
    assert message.deleted is False
    button = message.answers[0]["reply_markup"].inline_keyboard[0][0]
    assert button.web_app.url == "https://example.com/users?profile=alice&profile_token=test-token"


@pytest.mark.asyncio
async def test_users_shared_handler_ignores_current_user(monkeypatch) -> None:
    """test self selection ignored"""
    message = FakeMessage(
        users_shared=UsersShared(
            request_id=bot.FIND_FRIENDS_REQUEST_ID,
            users=[SharedUser(user_id=999, first_name="Current")],
        )
    )
    monkeypatch.setattr(bot, "_allow_find_request", _allow_request)

    await bot.users_shared_handler(message)

    assert message.answers == []
    assert message.deleted is True


async def _allow_request(telegram_id: int) -> bool:
    """allow test request"""
    return True


async def _create_discovery_token(redis, requester_telegram_id: int, target_telegram_id: int) -> str:
    """create test discovery token"""
    return "test-token"


class FakeMessage:
    """fake telegram message"""

    def __init__(self, users_shared=None) -> None:
        self.users_shared = users_shared
        self.from_user = SimpleNamespace(id=999, language_code="en")
        self.answers = []
        self.deleted = False

    async def answer(self, text, reply_markup=None, **kwargs) -> None:
        """capture answer"""
        self.answers.append({"text": text, "reply_markup": reply_markup, **kwargs})

    async def delete(self) -> None:
        """capture deletion"""
        self.deleted = True


class FakeSession:
    """fake database session"""

    def __init__(self, user) -> None:
        self.user = user

    async def __aenter__(self):
        """enter session"""
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        """exit session"""

    async def execute(self, statement):
        """return matching user"""
        return FakeResult(self.user)


class FakeResult:
    """fake query result"""

    def __init__(self, user) -> None:
        self.user = user

    def scalars(self):
        """return scalar result"""
        return self

    def all(self):
        """return users"""
        return [self.user]

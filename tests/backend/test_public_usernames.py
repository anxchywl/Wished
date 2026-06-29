from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.modules.users.service import (
    build_public_profile_url,
    build_telegram_startapp_url,
    ensure_public_username,
    get_user_by_public_username,
    is_valid_public_username,
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDb:
    def __init__(self, *values):
        self.values = list(values)

    async def execute(self, _statement):
        return FakeResult(self.values.pop(0) if self.values else None)


def test_public_username_validation_rejects_invalid_and_reserved_names():
    assert is_valid_public_username("max_472")
    assert is_valid_public_username("MAX_472")
    assert not is_valid_public_username("ab")
    assert not is_valid_public_username("max-472")
    assert not is_valid_public_username("admin")
    assert not is_valid_public_username("Users")


@pytest.mark.asyncio
async def test_ensure_public_username_uses_available_telegram_username(monkeypatch):
    async def username_exists(_db, _username):
        return False

    monkeypatch.setattr(
        "app.modules.users.service._public_username_exists", username_exists
    )
    user = SimpleNamespace(id=uuid4(), public_username=None)

    await ensure_public_username(FakeDb(), user, "Max_472")

    assert user.public_username == "max_472"


@pytest.mark.asyncio
async def test_ensure_public_username_falls_back_when_telegram_username_is_missing(
    monkeypatch,
):
    async def username_exists(_db, _username):
        return False

    monkeypatch.setattr(
        "app.modules.users.service._public_username_exists", username_exists
    )
    user = SimpleNamespace(id=uuid4(), public_username=None)

    await ensure_public_username(FakeDb(), user, None)

    assert user.public_username.startswith("u")
    assert is_valid_public_username(user.public_username)


@pytest.mark.asyncio
async def test_ensure_public_username_skips_taken_preferred_username(monkeypatch):
    async def username_exists(_db, username):
        return username == "max"

    monkeypatch.setattr(
        "app.modules.users.service._public_username_exists", username_exists
    )
    user = SimpleNamespace(id=uuid4(), public_username=None)

    await ensure_public_username(FakeDb(), user, "Max")

    assert user.public_username != "max"
    assert is_valid_public_username(user.public_username)


@pytest.mark.asyncio
async def test_get_user_by_public_username_resolves_current_username():
    user = SimpleNamespace(is_blocked=False)

    result = await get_user_by_public_username(FakeDb(user), "Max")

    assert result is user


@pytest.mark.asyncio
async def test_get_user_by_public_username_resolves_alias_username():
    user = SimpleNamespace(is_blocked=False)

    result = await get_user_by_public_username(FakeDb(None, user), "old_max")

    assert result is user


@pytest.mark.asyncio
async def test_get_user_by_public_username_returns_404_for_unknown_username():
    with pytest.raises(HTTPException) as exc:
        await get_user_by_public_username(FakeDb(None, None), "unknown")

    assert exc.value.status_code == 404


def test_profile_urls_are_generated_from_settings():
    user = SimpleNamespace(public_username="max")
    settings = Settings(
        public_web_app_url="https://wished.app",
        telegram_bot_username="wished_bot",
    )

    assert build_public_profile_url(user, settings) == "https://wished.app/@max"
    assert (
        build_telegram_startapp_url(user, settings)
        == "https://t.me/wished_bot?startapp=p_max"
    )

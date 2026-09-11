from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
from app.integrations.telegram import TelegramUserData
from app.main import create_app
from app.modules.auth.schemas import RefreshResponse, TokenResponse, UserResponse


def _fake_redis():
    """redis mock that always passes rate limiting"""
    r = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, True, 1, True])
    r.pipeline = MagicMock(return_value=pipe)
    return r


def test_telegram_auth_sets_access_token_and_refresh_cookie(monkeypatch) -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_settings] = _override_settings
    app.dependency_overrides[get_redis] = _fake_redis

    async def fake_authenticate_telegram_user(db, telegram_user, settings):
        assert telegram_user.telegram_id == 123456789
        return _token_response(), "refresh-token"

    def fake_validate_telegram_init_data(init_data, bot_token, max_age_seconds):
        assert init_data == "signed-init-data"
        return TelegramUserData(
            telegram_id=123456789,
            username="alice",
            first_name="Alice",
            last_name="Example",
            photo_url="https://example.com/photo.jpg",
            language_code="en",
            is_premium=False,
        )

    monkeypatch.setattr(
        "app.api.v1.auth.router.authenticate_telegram_user",
        fake_authenticate_telegram_user,
    )
    monkeypatch.setattr(
        "app.api.v1.auth.router.validate_telegram_init_data",
        fake_validate_telegram_init_data,
    )

    response = TestClient(app).post("/api/v1/auth/telegram", json={"init_data": "signed-init-data"})

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "access-token"
    assert "refresh_token" not in body
    assert body["user"]["telegram_id"] == 123456789
    assert "refresh_token" in response.cookies


def test_refresh_endpoint_rotates_refresh_token(monkeypatch) -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_settings] = _override_settings
    app.dependency_overrides[get_redis] = _fake_redis

    async def fake_refresh_tokens(db, refresh_token, settings):
        assert refresh_token == "old-refresh-token"
        return RefreshResponse(
            access_token="new-access-token",
            access_token_expires_at=datetime.now(UTC) + timedelta(minutes=15),
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
        ), "new-refresh-token"

    monkeypatch.setattr("app.api.v1.auth.router.refresh_tokens", fake_refresh_tokens)

    response = TestClient(app).post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "old-refresh-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "new-access-token"
    assert "refresh_token" not in body
    assert "refresh_token" in response.cookies


def test_refresh_endpoint_returns_401_without_cookie() -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_settings] = _override_settings
    app.dependency_overrides[get_redis] = _fake_redis

    response = TestClient(app).post("/api/v1/auth/refresh")

    assert response.status_code == 401


def test_logout_endpoint_revokes_refresh_token(monkeypatch) -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_settings] = _override_settings

    called = False

    async def fake_logout(db, refresh_token):
        nonlocal called
        called = True
        assert refresh_token == "refresh-token"

    monkeypatch.setattr("app.api.v1.auth.router.logout", fake_logout)

    response = TestClient(app).post(
        "/api/v1/auth/logout",
        cookies={"refresh_token": "refresh-token"},
    )

    assert response.status_code == 204
    assert called is True


def test_logout_endpoint_succeeds_without_cookie() -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_settings] = _override_settings

    response = TestClient(app).post("/api/v1/auth/logout")

    assert response.status_code == 204


def test_unversioned_auth_route_is_not_registered() -> None:
    response = TestClient(create_app()).post(
        "/auth/telegram",
        json={"init_data": "signed-init-data"},
    )

    assert response.status_code == 404


async def _override_db():
    yield object()


def _override_settings() -> Settings:
    return Settings(
        telegram_bot_token="test-token",
        jwt_secret_key="test-secret",
    )


def _token_response() -> TokenResponse:
    return TokenResponse(
        access_token="access-token",
        access_token_expires_at=datetime.now(UTC) + timedelta(minutes=15),
        refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
        user=UserResponse(
            id=uuid4(),
            telegram_id=123456789,
            username="alice",
            first_name="Alice",
            last_name="Example",
            photo_url="https://example.com/photo.jpg",
            language_code="en",
            is_premium=False,
        ),
    )


def test_telegram_auth_rejects_blocked_user(monkeypatch) -> None:
    import pytest
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.modules.auth import service as auth_service

    async def fake_get_or_create_user(db, telegram_user):
        return SimpleNamespace(is_blocked=True, blocked_reason="spam")

    monkeypatch.setattr(auth_service, "_get_or_create_user", fake_get_or_create_user)

    async def run():
        with pytest.raises(HTTPException) as exc:
            await auth_service.authenticate_telegram_user(
                db=AsyncMock(),
                telegram_user=SimpleNamespace(telegram_id=1),
                settings=MagicMock(),
            )
        assert exc.value.status_code == 403
        assert exc.value.detail == {"code": "account_blocked", "reason": "spam"}

    import asyncio

    asyncio.run(run())

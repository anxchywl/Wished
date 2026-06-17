from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps.database import get_db_session
from app.core.config import Settings, get_settings
from app.integrations.telegram import TelegramUserData
from app.main import create_app
from app.modules.auth.schemas import RefreshResponse, TokenResponse, UserResponse


def test_telegram_auth_endpoint_uses_validated_telegram_user(monkeypatch) -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_settings] = _override_settings

    async def fake_authenticate_telegram_user(db, telegram_user, settings):
        assert telegram_user.telegram_id == 123456789
        return _token_response()

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

    response = TestClient(app).post("/auth/telegram", json={"init_data": "signed-init-data"})

    assert response.status_code == 200
    assert response.json()["access_token"] == "access-token"
    assert response.json()["refresh_token"] == "refresh-token"
    assert response.json()["user"]["telegram_id"] == 123456789


def test_refresh_endpoint_rotates_refresh_token(monkeypatch) -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_settings] = _override_settings

    async def fake_refresh_tokens(db, refresh_token, settings):
        assert refresh_token == "old-refresh-token"
        return RefreshResponse(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            access_token_expires_at=datetime.now(UTC) + timedelta(minutes=15),
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
        )

    monkeypatch.setattr("app.api.v1.auth.router.refresh_tokens", fake_refresh_tokens)

    response = TestClient(app).post("/auth/refresh", json={"refresh_token": "old-refresh-token"})

    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access-token"
    assert response.json()["refresh_token"] == "new-refresh-token"


def test_logout_endpoint_revokes_refresh_token(monkeypatch) -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = _override_db

    called = False

    async def fake_logout(db, refresh_token):
        nonlocal called
        called = True
        assert refresh_token == "refresh-token"

    monkeypatch.setattr("app.api.v1.auth.router.logout", fake_logout)

    response = TestClient(app).post("/auth/logout", json={"refresh_token": "refresh-token"})

    assert response.status_code == 204
    assert called is True


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
        refresh_token="refresh-token",
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

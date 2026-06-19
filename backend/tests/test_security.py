"""security and privacy regression tests

covers findings from the 2026-06-19 security audit:
  C1 - direct MinIO proxy removed
  C2 - CORS middleware applied
  H1 - insecure JWT secret rejected in production
  H3 - Telegram initData replay window
  H4 - auth endpoint rate limiting
  M3 - wish URL scheme validation
  M4 - reservation race returns 409 not 500
  M5 - non-active wish cannot be reserved
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlencode
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
from app.main import create_app

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

BOT_TOKEN = "123456:test-token"


def _build_init_data(
    user: dict[str, Any],
    auth_date: datetime | None = None,
) -> str:
    payload = {
        "auth_date": str(int((auth_date or datetime.now(UTC)).timestamp())),
        "query_id": "test-query",
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    payload["hash"] = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(payload)


def _test_settings(**overrides: Any) -> Settings:
    return Settings(
        telegram_bot_token="test-token",
        jwt_secret_key="test-secret",
        **overrides,
    )


def _fake_redis_under_limit() -> AsyncMock:
    """redis mock that reports counts below all rate limits"""
    r = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, True, 1, True])
    r.pipeline = MagicMock(return_value=pipe)
    return r


def _fake_redis_minute_exceeded() -> AsyncMock:
    """redis mock that reports per-minute counter over the limit"""
    r = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[11, True, 1, True])
    r.pipeline = MagicMock(return_value=pipe)
    return r


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


# ---------------------------------------------------------------------------
# C2 — CORS middleware
# ---------------------------------------------------------------------------

class TestCORS:
    def test_cors_allows_configured_origin(self, monkeypatch) -> None:
        # CORS middleware is configured at create_app() time using the settings object,
        # so we must set the env var and clear the lru_cache before creating the app
        monkeypatch.setenv("ALLOWED_ORIGINS", '["https://example.com"]')
        from app.core.config import get_settings as _gs
        _gs.cache_clear()

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.options(
            "/api/v1/health",
            headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"},
        )
        assert response.headers.get("access-control-allow-origin") == "https://example.com"

        _gs.cache_clear()

    def test_cors_does_not_reflect_disallowed_origin(self, monkeypatch) -> None:
        monkeypatch.setenv("ALLOWED_ORIGINS", '["https://allowed.example.com"]')
        from app.core.config import get_settings as _gs
        _gs.cache_clear()

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.options(
            "/api/v1/health",
            headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"},
        )
        allow = response.headers.get("access-control-allow-origin", "")
        assert "evil.example.com" not in allow

        _gs.cache_clear()

    def test_cors_middleware_is_present_in_app(self) -> None:
        from starlette.middleware.cors import CORSMiddleware

        app = create_app()
        # user_middleware contains Middleware wrapper objects; cls holds the real class
        middleware_classes = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in middleware_classes


# ---------------------------------------------------------------------------
# H1 — insecure JWT secret rejected in production
# ---------------------------------------------------------------------------

class TestJWTSecretValidation:
    def test_create_app_raises_in_production_with_default_secret(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "change-me")

        # reset cached settings so the patched env takes effect
        from app.core.config import get_settings as _gs
        _gs.cache_clear()

        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            create_app()

        _gs.cache_clear()

    def test_create_app_raises_in_production_with_empty_secret(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "")

        from app.core.config import get_settings as _gs
        _gs.cache_clear()

        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            create_app()

        _gs.cache_clear()

    def test_create_app_succeeds_in_development_with_default_secret(self) -> None:
        # default app_env is development, so this must not raise
        app = create_app()
        assert app is not None


# ---------------------------------------------------------------------------
# H3 — Telegram initData replay window
# ---------------------------------------------------------------------------

class TestTelegramInitDataMaxAge:
    def test_default_max_age_is_300_seconds(self) -> None:
        from app.core.config import Settings
        s = Settings()
        assert s.telegram_init_data_max_age_seconds == 300

    def test_validate_telegram_init_data_rejects_six_minute_old_data(self) -> None:
        from app.integrations.telegram import TelegramInitDataError, validate_telegram_init_data

        init_data = _build_init_data(
            {"id": 1, "first_name": "Alice"},
            auth_date=datetime.now(UTC) - timedelta(minutes=6),
        )

        with pytest.raises(TelegramInitDataError, match="expired"):
            validate_telegram_init_data(
                init_data=init_data,
                bot_token=BOT_TOKEN,
                max_age_seconds=300,
            )

    def test_validate_telegram_init_data_accepts_fresh_data_within_window(self) -> None:
        from app.integrations.telegram import validate_telegram_init_data

        init_data = _build_init_data(
            {"id": 1, "first_name": "Alice"},
            auth_date=datetime.now(UTC) - timedelta(seconds=10),
        )

        user = validate_telegram_init_data(
            init_data=init_data,
            bot_token=BOT_TOKEN,
            max_age_seconds=300,
        )
        assert user.telegram_id == 1


# ---------------------------------------------------------------------------
# H4 — auth endpoint rate limiting
# ---------------------------------------------------------------------------

class TestAuthRateLimiting:
    def test_telegram_auth_returns_429_when_rate_limited(self, monkeypatch) -> None:
        app = create_app()
        app.dependency_overrides[get_db_session] = lambda: None
        app.dependency_overrides[get_settings] = lambda: _test_settings()
        app.dependency_overrides[get_redis] = _fake_redis_minute_exceeded

        response = TestClient(app).post(
            "/auth/telegram",
            json={"init_data": "whatever"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_refresh_returns_429_when_rate_limited(self, monkeypatch) -> None:
        app = create_app()
        app.dependency_overrides[get_db_session] = lambda: None
        app.dependency_overrides[get_settings] = lambda: _test_settings()
        app.dependency_overrides[get_redis] = _fake_redis_minute_exceeded

        response = TestClient(app).post(
            "/auth/refresh",
            json={"refresh_token": "whatever"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_telegram_auth_proceeds_within_limit(self, monkeypatch) -> None:
        """successful auth path when rate limit not exceeded"""
        from app.integrations.telegram import TelegramUserData
        from app.modules.auth.schemas import TokenResponse, UserResponse

        app = create_app()
        app.dependency_overrides[get_db_session] = lambda: None
        app.dependency_overrides[get_settings] = lambda: _test_settings()
        app.dependency_overrides[get_redis] = _fake_redis_under_limit

        def fake_validate(init_data: str, bot_token: str, max_age_seconds: int):
            return TelegramUserData(
                telegram_id=1,
                username=None,
                first_name="A",
                last_name=None,
                photo_url=None,
                language_code=None,
                is_premium=None,
            )

        async def fake_authenticate(db, telegram_user, settings):
            return TokenResponse(
                access_token="tok",
                refresh_token="rtok",
                access_token_expires_at=datetime.now(UTC) + timedelta(minutes=15),
                refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
                user=UserResponse(
                    id=uuid4(),
                    telegram_id=1,
                    username=None,
                    first_name="A",
                    last_name=None,
                    photo_url=None,
                    language_code=None,
                    is_premium=None,
                ),
            )

        monkeypatch.setattr("app.api.v1.auth.router.validate_telegram_init_data", fake_validate)
        monkeypatch.setattr("app.api.v1.auth.router.authenticate_telegram_user", fake_authenticate)

        response = TestClient(app).post("/auth/telegram", json={"init_data": "data"})
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_rate_limit_raises_429_when_minute_exceeded() -> None:
    from app.modules.auth.rate_limit import check_auth_rate_limit
    from fastapi import HTTPException, Request

    request = MagicMock(spec=Request)
    request.headers = {"X-Forwarded-For": ""}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    redis = _fake_redis_minute_exceeded()

    with pytest.raises(HTTPException) as exc_info:
        await check_auth_rate_limit(redis, request)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_auth_rate_limit_passes_within_limits() -> None:
    from app.modules.auth.rate_limit import check_auth_rate_limit
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.headers = {"X-Forwarded-For": ""}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    redis = _fake_redis_under_limit()
    # must not raise
    await check_auth_rate_limit(redis, request)


# ---------------------------------------------------------------------------
# M3 — wish URL scheme validation
# ---------------------------------------------------------------------------

class TestWishURLValidation:
    def test_rejects_javascript_url(self) -> None:
        from app.modules.wishes.schemas import WishCreateRequest
        import pydantic

        with pytest.raises(pydantic.ValidationError, match="http or https"):
            WishCreateRequest(title="bad", url="javascript:alert(1)")

    def test_rejects_data_url(self) -> None:
        from app.modules.wishes.schemas import WishCreateRequest
        import pydantic

        with pytest.raises(pydantic.ValidationError, match="http or https"):
            WishCreateRequest(title="bad", url="data:text/html,<script>alert(1)</script>")

    def test_rejects_file_url(self) -> None:
        from app.modules.wishes.schemas import WishCreateRequest
        import pydantic

        with pytest.raises(pydantic.ValidationError, match="http or https"):
            WishCreateRequest(title="bad", url="file:///etc/passwd")

    def test_accepts_https_url(self) -> None:
        from app.modules.wishes.schemas import WishCreateRequest

        req = WishCreateRequest(title="valid", url="https://example.com/product")
        assert req.url == "https://example.com/product"

    def test_accepts_http_url(self) -> None:
        from app.modules.wishes.schemas import WishCreateRequest

        req = WishCreateRequest(title="valid", url="http://example.com/product")
        assert req.url == "http://example.com/product"

    def test_accepts_none_url(self) -> None:
        from app.modules.wishes.schemas import WishCreateRequest

        req = WishCreateRequest(title="no url")
        assert req.url is None

    def test_update_request_rejects_javascript_url(self) -> None:
        from app.modules.wishes.schemas import WishUpdateRequest
        import pydantic

        with pytest.raises(pydantic.ValidationError, match="http or https"):
            WishUpdateRequest(url="javascript:void(0)")

    def test_create_wish_via_api_rejects_unsafe_url(self, monkeypatch) -> None:
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: _user()
        app.dependency_overrides[get_db_session] = lambda: None

        response = TestClient(app).post(
            f"/wishlists/{uuid4()}/wishes",
            json={"title": "Bad", "url": "javascript:alert(1)"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# M4 — reservation race condition returns 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reservation_integrity_error_raises_409() -> None:
    from sqlalchemy.exc import IntegrityError
    from app.modules.reservations.service import create_reservation
    from fastapi import HTTPException

    db = AsyncMock()

    # first select (FOR UPDATE) returns no existing reservation
    active_result = AsyncMock()
    active_result.scalar_one_or_none = MagicMock(return_value=None)

    # accessible wish result
    wish_mock = MagicMock()
    wish_mock.status = "active"
    wish_mock.wishlist.owner_user_id = uuid4()
    wish_mock.wishlist.visibility = "public"
    accessible_result = AsyncMock()
    accessible_result.scalar_one_or_none = MagicMock(return_value=wish_mock)

    db.execute = AsyncMock(side_effect=[accessible_result, active_result])
    db.add = MagicMock()
    db.commit = AsyncMock(side_effect=IntegrityError("unique violation", {}, None))
    db.rollback = AsyncMock()

    current_user = MagicMock()
    current_user.id = uuid4()
    # make sure user is not the owner
    wish_mock.wishlist.owner_user_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await create_reservation(db, current_user, uuid4())

    assert exc_info.value.status_code == 409
    db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# M5 — non-active wish cannot be reserved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cannot_reserve_completed_wish() -> None:
    from app.modules.reservations.service import create_reservation
    from fastapi import HTTPException

    db = AsyncMock()

    wish_mock = MagicMock()
    wish_mock.status = "completed"
    owner_id = uuid4()
    wish_mock.wishlist.owner_user_id = owner_id
    wish_mock.wishlist.visibility = "public"

    result = AsyncMock()
    result.scalar_one_or_none = MagicMock(return_value=wish_mock)
    db.execute = AsyncMock(return_value=result)

    current_user = MagicMock()
    current_user.id = uuid4()  # different from owner

    with pytest.raises(HTTPException) as exc_info:
        await create_reservation(db, current_user, uuid4())

    assert exc_info.value.status_code == 409
    assert "not available" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cannot_reserve_archived_wish() -> None:
    from app.modules.reservations.service import create_reservation
    from fastapi import HTTPException

    db = AsyncMock()

    wish_mock = MagicMock()
    wish_mock.status = "archived"
    wish_mock.wishlist.owner_user_id = uuid4()
    wish_mock.wishlist.visibility = "public"

    result = AsyncMock()
    result.scalar_one_or_none = MagicMock(return_value=wish_mock)
    db.execute = AsyncMock(return_value=result)

    current_user = MagicMock()
    current_user.id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await create_reservation(db, current_user, uuid4())

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_can_reserve_active_wish() -> None:
    """active wish reservation proceeds past the status check"""
    from app.modules.reservations.service import _get_accessible_wish

    db = AsyncMock()

    wish_mock = MagicMock()
    wish_mock.status = "active"
    wish_mock.wishlist.owner_user_id = uuid4()
    wish_mock.wishlist.visibility = "public"

    result = AsyncMock()
    result.scalar_one_or_none = MagicMock(return_value=wish_mock)
    db.execute = AsyncMock(return_value=result)

    current_user = MagicMock()
    current_user.id = uuid4()

    returned = await _get_accessible_wish(db, current_user, uuid4())
    assert returned is wish_mock


# ---------------------------------------------------------------------------
# media access authorization (C1 regression)
# ---------------------------------------------------------------------------

class TestMediaAccessAuthorization:
    def test_media_endpoint_requires_authentication(self) -> None:
        """GET /media/{id} must return 401 without a token, not redirect to MinIO"""
        app = create_app()
        # do not override get_current_user — let auth dependency enforce itself
        app.dependency_overrides[get_db_session] = lambda: None

        response = TestClient(app, raise_server_exceptions=False).get(
            f"/media/{uuid4()}"
        )
        assert response.status_code == 401

    def test_wish_images_endpoint_requires_authentication(self) -> None:
        app = create_app()
        app.dependency_overrides[get_db_session] = lambda: None

        response = TestClient(app, raise_server_exceptions=False).get(
            f"/wishes/{uuid4()}/images"
        )
        assert response.status_code == 401

    def test_no_minio_route_in_caddy_config(self) -> None:
        """verify the Caddyfile no longer has a direct MinIO proxy rule"""
        import os

        caddyfile_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "infra", "caddy", "Caddyfile",
        )
        if not os.path.exists(caddyfile_path):
            pytest.skip("Caddyfile not found at expected path")

        with open(caddyfile_path) as f:
            content = f.read()

        # the direct MinIO bucket proxy must be absent
        assert "wished-media" not in content
        assert "minio:9000" not in content


# ---------------------------------------------------------------------------
# validation error handler does not leak request body (M1)
# ---------------------------------------------------------------------------

class TestValidationErrorHandler:
    def test_validation_error_response_excludes_input_value(self) -> None:
        """422 response must not echo back the raw request value"""
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: _user()
        app.dependency_overrides[get_db_session] = lambda: None

        secret_value = "super-secret-init-data-token"
        response = TestClient(app).post(
            f"/wishlists/{uuid4()}/wishes",
            json={"title": "test", "url": secret_value},  # url fails scheme validation
        )

        assert response.status_code == 422
        response_text = response.text
        # the raw secret value must not appear in the error response
        assert secret_value not in response_text

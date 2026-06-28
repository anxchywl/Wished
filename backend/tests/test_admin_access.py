"""
tests proving that admin authorization is server-side enforced.

non-admins cannot access admin routes or apis.
admins can access admin routes and apis.
privilege escalation and direct api bypass are impossible.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
from app.core.security.jwt import create_access_token
from app.db.models.users import User
from app.main import create_app

ADMIN_TELEGRAM_ID = 111111
NON_ADMIN_TELEGRAM_ID = 999999

ADMIN_SETTINGS = Settings(
    jwt_secret_key="test-secret-key-that-is-long-enough",
    telegram_bot_token="test-bot-token",
    admin_telegram_ids=[ADMIN_TELEGRAM_ID],
)

NON_ADMIN_SETTINGS = Settings(
    jwt_secret_key="test-secret-key-that-is-long-enough",
    telegram_bot_token="test-bot-token",
    admin_telegram_ids=[ADMIN_TELEGRAM_ID],
)


def _make_user(telegram_id: int) -> User:
    user = User()
    user.id = uuid4()
    user.telegram_id = telegram_id
    user.username = f"user_{telegram_id}"
    user.first_name = "Test"
    user.last_name = "User"
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    user.last_login_at = datetime.now(UTC)
    user.profile_visibility = "friends"
    user.birthday_visibility = "friends"
    user.wishlist_visibility = "friends"
    user.booking_visibility = "hide"
    return user


def _make_token(telegram_id: int, settings: Settings) -> str:
    user_id = uuid4()
    token, _ = create_access_token(user_id, settings)
    return token


def _fake_db(user: User) -> AsyncMock:
    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)

    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=user)
    result.scalar = MagicMock(return_value=0)
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    result.all = MagicMock(return_value=[])
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    return db


def _fake_redis() -> AsyncMock:
    r = AsyncMock()
    r.ping = AsyncMock(return_value=True)
    return r


def _make_client(user: User, settings: Settings) -> tuple[TestClient, str]:
    app = create_app()
    db_instance = _fake_db(user)

    async def override_db():
        yield db_instance

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_redis] = _fake_redis
    token = _make_token(user.telegram_id, settings)
    return TestClient(app, raise_server_exceptions=False), token


ADMIN_ENDPOINTS = [
    ("GET", "/api/v1/admin/me"),
    ("GET", "/api/v1/admin/stats"),
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/wishlists"),
    ("GET", "/api/v1/admin/wishes"),
    ("GET", "/api/v1/admin/media"),
    ("GET", "/api/v1/admin/audit-logs"),
]


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
def test_non_admin_user_cannot_access_admin_api(method: str, path: str) -> None:
    """non-admin with a valid token must receive 403 on all admin endpoints"""
    user = _make_user(NON_ADMIN_TELEGRAM_ID)
    client, token = _make_client(user, NON_ADMIN_SETTINGS)

    response = client.request(method, path, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403, (
        f"{method} {path} returned {response.status_code} instead of 403 for non-admin"
    )


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
def test_unauthenticated_request_cannot_access_admin_api(method: str, path: str) -> None:
    """requests without a token must receive 401 or 403 on all admin endpoints"""
    user = _make_user(NON_ADMIN_TELEGRAM_ID)
    client, _ = _make_client(user, NON_ADMIN_SETTINGS)

    response = client.request(method, path)

    assert response.status_code in (401, 403), (
        f"{method} {path} returned {response.status_code} instead of 401/403 for unauthenticated request"
    )


def test_admin_me_returns_200_for_admin_user() -> None:
    """admin user with correct telegram id must receive 200 on /admin/me"""
    user = _make_user(ADMIN_TELEGRAM_ID)
    client, token = _make_client(user, ADMIN_SETTINGS)

    response = client.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["is_admin"] is True
    assert data["telegram_id"] == ADMIN_TELEGRAM_ID


def test_admin_me_returns_403_for_non_admin_user() -> None:
    """user not in admin_telegram_ids must receive 403 even with valid token"""
    user = _make_user(NON_ADMIN_TELEGRAM_ID)
    client, token = _make_client(user, NON_ADMIN_SETTINGS)

    response = client.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_non_admin_cannot_access_stats() -> None:
    """non-admin cannot read aggregate stats"""
    user = _make_user(NON_ADMIN_TELEGRAM_ID)
    client, token = _make_client(user, NON_ADMIN_SETTINGS)

    response = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_non_admin_cannot_list_users() -> None:
    """non-admin cannot enumerate platform users"""
    user = _make_user(NON_ADMIN_TELEGRAM_ID)
    client, token = _make_client(user, NON_ADMIN_SETTINGS)

    response = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_non_admin_cannot_view_audit_logs() -> None:
    """non-admin cannot read audit trail"""
    user = _make_user(NON_ADMIN_TELEGRAM_ID)
    client, token = _make_client(user, NON_ADMIN_SETTINGS)

    response = client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_privilege_escalation_impossible_via_query_params() -> None:
    """passing admin=true or role=admin in query params does not grant access"""
    user = _make_user(NON_ADMIN_TELEGRAM_ID)
    client, token = _make_client(user, NON_ADMIN_SETTINGS)

    response = client.get(
        "/api/v1/admin/stats?admin=true&role=admin&is_admin=1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_privilege_escalation_impossible_via_request_body() -> None:
    """sending is_admin in request body does not grant admin access"""
    user = _make_user(NON_ADMIN_TELEGRAM_ID)
    client, token = _make_client(user, NON_ADMIN_SETTINGS)

    # send a forged body claiming admin — must never result in access granted
    response = client.request(
        "GET",
        "/api/v1/admin/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_admin": True, "role": "admin"},
    )

    assert response.status_code != 200, "Body-injected admin claim must not grant admin access"


def test_is_admin_dependency_uses_env_ids_not_db_role() -> None:
    """admin access is determined by ADMIN_TELEGRAM_IDS env var, not a db role field"""
    # user has same telegram_id that is in admin_ids
    user = _make_user(ADMIN_TELEGRAM_ID)
    client, token = _make_client(user, ADMIN_SETTINGS)

    response = client.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    # user with non-admin telegram_id is rejected even though it's the same db session
    user_non_admin = _make_user(NON_ADMIN_TELEGRAM_ID)
    client2, token2 = _make_client(user_non_admin, ADMIN_SETTINGS)
    response2 = client2.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {token2}"})
    assert response2.status_code == 403

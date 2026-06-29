from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.main import create_app


def _fake_redis():
    return AsyncMock()


def test_get_user_profile_returns_profile(monkeypatch) -> None:
    """test profile route"""
    app = create_app()
    current_user = _user(username="alice")
    target_user = _user(username="bob")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_redis] = _fake_redis

    async def fake_get_user_by_username(db, username):
        assert username == "bob"
        return target_user

    async def fake_validate_discovery_token(
        redis, token, requester_tid, target_tid, db=None
    ):
        return False

    async def fake_is_following_user(db, current_user, user):
        return False

    monkeypatch.setattr(
        "app.api.v1.users.router.get_user_by_username", fake_get_user_by_username
    )
    monkeypatch.setattr(
        "app.api.v1.users.router.validate_discovery_token",
        fake_validate_discovery_token,
    )
    monkeypatch.setattr(
        "app.api.v1.users.router.is_following_user", fake_is_following_user
    )

    response = TestClient(app).get("/api/v1/users/bob")

    assert response.status_code == 200
    assert response.json()["username"] == "bob"
    assert "id" not in response.json()


def test_get_user_profile_by_public_username_returns_profile(monkeypatch) -> None:
    """test public username profile route"""
    app = create_app()
    current_user = _user(username="alice")
    target_user = _user(username="bob")
    target_user.public_username = "max"
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_redis] = _fake_redis

    async def fake_get_user_by_public_username(db, public_username):
        assert public_username == "max"
        return target_user

    async def fake_validate_discovery_token(
        redis, token, requester_tid, target_tid, db=None
    ):
        return False

    async def fake_is_following_user(db, current_user, user):
        return False

    async def fake_check_public_username_resolve_limit(redis, user_id, per_hour):
        return None

    monkeypatch.setattr(
        "app.api.v1.users.router.get_user_by_public_username",
        fake_get_user_by_public_username,
    )
    monkeypatch.setattr(
        "app.api.v1.users.router.validate_discovery_token",
        fake_validate_discovery_token,
    )
    monkeypatch.setattr(
        "app.api.v1.users.router.is_following_user",
        fake_is_following_user,
    )
    monkeypatch.setattr(
        "app.api.v1.users.router.check_public_username_resolve_limit",
        fake_check_public_username_resolve_limit,
    )

    response = TestClient(app).get("/api/v1/users/public/max")

    assert response.status_code == 200
    assert response.json()["user_id"] == str(target_user.id)
    assert response.json()["public_username"] == "max"
    assert response.json()["public_profile_url"] == "http://localhost:3000/@max"


def test_get_private_user_profile_returns_not_found(monkeypatch) -> None:
    """test private profile hidden"""
    app = create_app()
    current_user = _user(username="alice")
    target_user = _user(username="bob")
    target_user.profile_visibility = "private"
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_redis] = _fake_redis

    async def fake_get_user_by_username(db, username):
        return target_user

    async def fake_validate_discovery_token(
        redis, token, requester_tid, target_tid, db=None
    ):
        return False

    async def fake_is_following_user(db, current_user, user):
        return False

    monkeypatch.setattr(
        "app.api.v1.users.router.get_user_by_username", fake_get_user_by_username
    )
    monkeypatch.setattr(
        "app.api.v1.users.router.validate_discovery_token",
        fake_validate_discovery_token,
    )
    monkeypatch.setattr(
        "app.api.v1.users.router.is_following_user", fake_is_following_user
    )

    response = TestClient(app).get("/api/v1/users/bob")

    assert response.status_code == 404


def test_get_user_wishlists_returns_visible_wishlists(monkeypatch) -> None:
    """test user wishlists route"""
    app = create_app()
    current_user = _user(username="alice")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_redis] = _fake_redis

    async def fake_list_user_wishlists(
        db,
        current_user_arg,
        username,
        allow_profile_access=False,
    ):
        assert current_user_arg is current_user
        assert username == "bob"
        return {"items": []}

    async def fake_get_user_by_username(db, username):
        return _user(username="bob")

    async def fake_validate_discovery_token(
        redis, token, requester_tid, target_tid, db=None
    ):
        return False

    async def fake_is_following_user(db, current_user, user):
        return False

    monkeypatch.setattr(
        "app.api.v1.users.router.get_user_by_username", fake_get_user_by_username
    )
    monkeypatch.setattr(
        "app.api.v1.users.router.list_user_wishlists", fake_list_user_wishlists
    )
    monkeypatch.setattr(
        "app.api.v1.users.router.validate_discovery_token",
        fake_validate_discovery_token,
    )
    monkeypatch.setattr(
        "app.api.v1.users.router.is_following_user", fake_is_following_user
    )

    response = TestClient(app).get("/api/v1/users/bob/wishlists")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def _user(username: str = "alice") -> SimpleNamespace:
    """build test user"""
    timestamp = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid4(),
        telegram_id=123456789,
        username=username,
        first_name=username.title(),
        last_name="Example",
        photo_url=None,
        language_code="en",
        is_premium=False,
        birthday=date(1995, 4, 20),
        profile_visibility="public",
        birthday_visibility="private",
        wishlist_visibility="public",
        created_at=timestamp,
        updated_at=timestamp,
        last_login_at=timestamp,
    )

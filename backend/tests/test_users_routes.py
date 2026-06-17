from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.main import create_app


def test_search_users_uses_query_and_current_user(monkeypatch) -> None:
    """test user search route"""
    app = create_app()
    user = _user()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_search_users(db, query, current_user):
        assert query == "bob"
        assert current_user is user
        return [_search_user()]

    monkeypatch.setattr("app.api.v1.users.router.search_users", fake_search_users)

    response = TestClient(app).get("/users/search?q=bob")

    assert response.status_code == 200
    assert response.json()[0]["username"] == "bob"


def test_get_user_profile_returns_profile(monkeypatch) -> None:
    """test profile route"""
    app = create_app()
    current_user = _user(username="alice")
    target_user = _user(username="bob")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_get_user_by_username(db, username):
        assert username == "bob"
        return target_user

    monkeypatch.setattr("app.api.v1.users.router.get_user_by_username", fake_get_user_by_username)

    response = TestClient(app).get("/users/bob")

    assert response.status_code == 200
    assert response.json()["username"] == "bob"


def test_get_user_wishlists_returns_visible_wishlists(monkeypatch) -> None:
    """test user wishlists route"""
    app = create_app()
    current_user = _user(username="alice")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_list_user_wishlists(db, current_user_arg, username):
        assert current_user_arg is current_user
        assert username == "bob"
        return {"items": []}

    monkeypatch.setattr("app.api.v1.users.router.list_user_wishlists", fake_list_user_wishlists)

    response = TestClient(app).get("/users/bob/wishlists")

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


def _search_user() -> dict[str, object]:
    """build search user"""
    return {
        "id": uuid4(),
        "username": "bob",
        "first_name": "Bob",
        "last_name": "Example",
        "photo_url": None,
    }


from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.main import create_app


def test_get_me_returns_current_profile() -> None:
    app = create_app()
    user = _user()
    app.dependency_overrides[get_current_user] = lambda: user

    response = TestClient(app).get("/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "telegram_id": 123456789,
        "username": "alice",
        "first_name": "Alice",
        "last_name": "Example",
        "photo_url": "https://example.com/photo.jpg",
        "language_code": "en",
        "is_premium": False,
        "birthday": "1995-04-20",
        "privacy": {
            "profile_visibility": "public",
            "birthday_visibility": "private",
            "wishlist_visibility": "public",
        },
        "created_at": "2026-06-14T10:00:00Z",
        "updated_at": "2026-06-14T10:00:00Z",
        "last_login_at": "2026-06-14T10:00:00Z",
    }


def test_patch_me_updates_profile_fields() -> None:
    app = create_app()
    user = _user()
    db = FakeDb()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: db

    response = TestClient(app).patch(
        "/me",
        json={
            "birthday": None,
            "privacy": {
                "birthday_visibility": "private",
                "wishlist_visibility": "private",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["birthday"] is None
    assert response.json()["privacy"] == {
        "profile_visibility": "public",
        "birthday_visibility": "private",
        "wishlist_visibility": "private",
    }
    assert user.birthday is None
    assert user.birthday_visibility == "private"
    assert user.wishlist_visibility == "private"
    assert db.committed is True
    assert db.refreshed_user is user


def test_patch_me_rejects_future_birthday() -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db_session] = lambda: FakeDb()

    response = TestClient(app).patch("/me", json={"birthday": "2999-01-01"})

    assert response.status_code == 422


def test_patch_me_rejects_read_only_telegram_fields() -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db_session] = lambda: FakeDb()

    response = TestClient(app).patch("/me", json={"username": "mallory"})

    assert response.status_code == 422


class FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed_user = None

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, user) -> None:
        self.refreshed_user = user


def _user() -> SimpleNamespace:
    timestamp = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid4(),
        telegram_id=123456789,
        username="alice",
        first_name="Alice",
        last_name="Example",
        photo_url="https://example.com/photo.jpg",
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

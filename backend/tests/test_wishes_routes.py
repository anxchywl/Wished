from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.main import create_app


def _rate_limit_redis() -> AsyncMock:
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, True, 1, True])
    redis.pipeline = MagicMock(return_value=pipe)
    return redis


def test_list_wishes_returns_wishlist_wishes(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wishlist_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_redis] = _rate_limit_redis

    async def fake_list_wishlist_wishes(db, current_user, requested_wishlist_id, **kwargs):
        assert current_user is user
        assert requested_wishlist_id == wishlist_id
        return {"items": [_wish(wishlist_id=wishlist_id)]}

    monkeypatch.setattr("app.api.v1.wishes.router.list_wishlist_wishes", fake_list_wishlist_wishes)

    response = TestClient(app).get(f"/api/v1/wishlists/{wishlist_id}/wishes")

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Noise-cancelling headphones"


def test_create_wish_accepts_price_currency_and_priority(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wishlist_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_redis] = _rate_limit_redis

    async def fake_create_wish(db, current_user, requested_wishlist_id, payload, settings=None, redis=None):
        assert current_user is user
        assert requested_wishlist_id == wishlist_id
        assert payload.title == "Keyboard"
        assert payload.price == Decimal("129.99")
        assert payload.currency == "USD"
        assert payload.priority == 2
        return _wish(
            wishlist_id=wishlist_id,
            title=payload.title,
            price=payload.price,
            currency=payload.currency,
            priority=payload.priority,
        )

    monkeypatch.setattr("app.api.v1.wishes.router.create_wish", fake_create_wish)

    response = TestClient(app).post(
        f"/api/v1/wishlists/{wishlist_id}/wishes",
        json={
            "title": " Keyboard ",
            "priority": 2,
            "price": "129.99",
            "currency": "usd",
        },
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Keyboard"
    assert response.json()["price"] == "129.99"
    assert response.json()["currency"] == "USD"
    assert response.json()["priority"] == 2


def test_patch_wish_can_move_between_wishlists(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wish_id = uuid4()
    target_wishlist_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_redis] = _rate_limit_redis

    async def fake_update_wish(db, current_user, requested_wish_id, payload, redis=None):
        assert current_user is user
        assert requested_wish_id == wish_id
        assert payload.wishlist_id == target_wishlist_id
        return _wish(wishlist_id=target_wishlist_id)

    monkeypatch.setattr("app.api.v1.wishes.router.update_wish", fake_update_wish)

    response = TestClient(app).patch(
        f"/api/v1/wishes/{wish_id}",
        json={"wishlist_id": str(target_wishlist_id)},
    )

    assert response.status_code == 200
    assert response.json()["wishlist_id"] == str(target_wishlist_id)


def test_patch_wish_reorder_uses_payload(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wishlist_id = uuid4()
    wish_ids = [uuid4(), uuid4(), uuid4()]
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_reorder_wishes(db, current_user, requested_wishlist_id, payload, redis=None):
        assert current_user is user
        assert requested_wishlist_id == wishlist_id
        assert payload.wish_ids == wish_ids
        return {"items": [_wish(wishlist_id=wishlist_id, wish_id=wish_id, position=index) for index, wish_id in enumerate(wish_ids)]}

    monkeypatch.setattr("app.api.v1.wishes.router.reorder_wishes", fake_reorder_wishes)

    response = TestClient(app).patch(
        f"/api/v1/wishlists/{wishlist_id}/wishes/reorder",
        json={"wish_ids": [str(wish_id) for wish_id in wish_ids]},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(wish_id) for wish_id in wish_ids]
    assert response.json()["items"][2]["position"] == 2


def test_patch_wish_reorder_rejects_duplicate_ids() -> None:
    app = create_app()
    wishlist_id = uuid4()
    wish_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db_session] = lambda: object()

    response = TestClient(app).patch(
        f"/api/v1/wishlists/{wishlist_id}/wishes/reorder",
        json={"wish_ids": [str(wish_id), str(wish_id)]},
    )

    assert response.status_code == 422


def test_delete_wish_returns_no_content(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wish_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_redis] = _rate_limit_redis

    async def fake_delete_wish(db, current_user, requested_wish_id, redis=None):
        assert current_user is user
        assert requested_wish_id == wish_id

    monkeypatch.setattr("app.api.v1.wishes.router.delete_wish", fake_delete_wish)

    response = TestClient(app).delete(f"/api/v1/wishes/{wish_id}")

    assert response.status_code == 204


def test_copy_wish_uses_target_wishlist(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wish_id = uuid4()
    target_wishlist_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_copy_wish(db, current_user, requested_wish_id, payload, redis=None):
        assert current_user is user
        assert requested_wish_id == wish_id
        assert payload.wishlist_id == target_wishlist_id
        return _wish(wishlist_id=target_wishlist_id, title="Copied wish")

    monkeypatch.setattr("app.api.v1.wishes.router.copy_wish", fake_copy_wish)

    response = TestClient(app).post(
        f"/api/v1/wishes/{wish_id}/copy",
        json={"wishlist_id": str(target_wishlist_id)},
    )

    assert response.status_code == 201
    assert response.json()["wishlist_id"] == str(target_wishlist_id)
    assert response.json()["title"] == "Copied wish"


def test_create_wish_rejects_price_without_currency() -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db_session] = lambda: object()

    response = TestClient(app).post(
        f"/api/v1/wishlists/{uuid4()}/wishes",
        json={"title": "Keyboard", "price": "129.99"},
    )

    assert response.status_code == 422


def test_create_wish_rejects_invalid_priority() -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db_session] = lambda: object()

    response = TestClient(app).post(
        f"/api/v1/wishlists/{uuid4()}/wishes",
        json={"title": "Keyboard", "priority": 9},
    )

    assert response.status_code == 422


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def _wish(
    wishlist_id: UUID,
    wish_id: UUID | None = None,
    title: str = "Noise-cancelling headphones",
    price: Decimal | None = Decimal("249.99"),
    currency: str | None = "USD",
    priority: int = 3,
    position: int = 0,
    status: str = "active",
) -> dict[str, object]:
    timestamp = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    return {
        "id": wish_id or uuid4(),
        "wishlist_id": wishlist_id,
        "title": title,
        "description": None,
        "url": None,
        "priority": priority,
        "position": position,
        "price": price,
        "currency": currency,
        "status": status,
        "original_product_url": None,
        "source_marketplace": None,
        "images": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }

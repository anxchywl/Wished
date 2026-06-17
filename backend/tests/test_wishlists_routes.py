from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.main import create_app


def test_list_wishlists_returns_current_user_wishlists(monkeypatch) -> None:
    app = create_app()
    user = _user()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_list_current_user_wishlists(db, current_user):
        assert current_user is user
        return {"items": [_wishlist(owner_user_id=user.id)]}

    monkeypatch.setattr(
        "app.api.v1.wishlists.router.list_current_user_wishlists",
        fake_list_current_user_wishlists,
    )

    response = TestClient(app).get("/wishlists")

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Birthday"


def test_create_wishlist_uses_payload_and_current_user(monkeypatch) -> None:
    app = create_app()
    user = _user()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_create_wishlist(db, current_user, payload):
        assert current_user is user
        assert payload.title == "Books"
        assert payload.description == "Things to read"
        assert payload.visibility == "private"
        return _wishlist(owner_user_id=user.id, title=payload.title, visibility=payload.visibility)

    monkeypatch.setattr("app.api.v1.wishlists.router.create_wishlist", fake_create_wishlist)

    response = TestClient(app).post(
        "/wishlists",
        json={"title": " Books ", "description": " Things to read ", "visibility": "private"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Books"
    assert response.json()["visibility"] == "private"


def test_get_wishlist_uses_accessible_wishlist(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wishlist_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_get_wishlist(db, current_user, requested_wishlist_id):
        assert current_user is user
        assert requested_wishlist_id == wishlist_id
        return _wishlist(owner_user_id=user.id)

    monkeypatch.setattr("app.api.v1.wishlists.router.get_wishlist", fake_get_wishlist)

    response = TestClient(app).get(f"/wishlists/{wishlist_id}")

    assert response.status_code == 200
    assert response.json()["visibility"] == "public"


def test_patch_wishlist_reorder_uses_payload(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wishlist_ids = [uuid4(), uuid4(), uuid4()]
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_reorder_wishlists(db, current_user, payload):
        assert current_user is user
        assert payload.wishlist_ids == wishlist_ids
        return {"items": [_wishlist(owner_user_id=user.id, wishlist_id=wishlist_id, position=index) for index, wishlist_id in enumerate(wishlist_ids)]}

    monkeypatch.setattr("app.api.v1.wishlists.router.reorder_wishlists", fake_reorder_wishlists)

    response = TestClient(app).patch(
        "/wishlists/reorder",
        json={"wishlist_ids": [str(wishlist_id) for wishlist_id in wishlist_ids]},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(wishlist_id) for wishlist_id in wishlist_ids]
    assert response.json()["items"][1]["position"] == 1


def test_patch_wishlist_reorder_rejects_duplicate_ids() -> None:
    app = create_app()
    wishlist_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db_session] = lambda: object()

    response = TestClient(app).patch(
        "/wishlists/reorder",
        json={"wishlist_ids": [str(wishlist_id), str(wishlist_id)]},
    )

    assert response.status_code == 422


def test_patch_wishlist_rejects_null_title() -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db_session] = lambda: object()

    response = TestClient(app).patch(f"/wishlists/{uuid4()}", json={"title": None})

    assert response.status_code == 422


def test_delete_wishlist_returns_no_content(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wishlist_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_delete_wishlist(db, current_user, requested_wishlist_id):
        assert current_user is user
        assert requested_wishlist_id == wishlist_id

    monkeypatch.setattr("app.api.v1.wishlists.router.delete_wishlist", fake_delete_wishlist)

    response = TestClient(app).delete(f"/wishlists/{wishlist_id}")

    assert response.status_code == 204


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), wishlist_visibility="public")


def _wishlist(
    owner_user_id: UUID,
    wishlist_id: UUID | None = None,
    title: str = "Birthday",
    visibility: str = "public",
    position: int = 0,
) -> dict[str, object]:
    timestamp = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    return {
        "id": wishlist_id or uuid4(),
        "owner_user_id": owner_user_id,
        "title": title,
        "description": None,
        "visibility": visibility,
        "position": position,
        "created_at": timestamp,
        "updated_at": timestamp,
    }

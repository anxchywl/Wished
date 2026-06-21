from io import BytesIO
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
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

    response = TestClient(app).get("/api/v1/wishlists")

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Birthday"


def test_create_wishlist_uses_payload_and_current_user(monkeypatch) -> None:
    app = create_app()
    user = _user()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_redis] = lambda: AsyncMock()

    async def fake_create_wishlist(db, current_user, payload, redis=None):
        assert current_user is user
        assert payload.title == "Books"
        assert payload.description == "Things to read"
        assert payload.visibility == "private"
        return _wishlist(owner_user_id=user.id, title=payload.title, visibility=payload.visibility)

    monkeypatch.setattr("app.api.v1.wishlists.router.create_wishlist", fake_create_wishlist)

    response = TestClient(app).post(
        "/api/v1/wishlists",
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

    response = TestClient(app).get(f"/api/v1/wishlists/{wishlist_id}")

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
        "/api/v1/wishlists/reorder",
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
        "/api/v1/wishlists/reorder",
        json={"wishlist_ids": [str(wishlist_id), str(wishlist_id)]},
    )

    assert response.status_code == 422


def test_patch_wishlist_rejects_null_title() -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db_session] = lambda: object()

    response = TestClient(app).patch(f"/api/v1/wishlists/{uuid4()}", json={"title": None})

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

    response = TestClient(app).delete(f"/api/v1/wishlists/{wishlist_id}")

    assert response.status_code == 204


def test_upload_wishlist_cover_passes_file_and_security_dependencies(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wishlist_id = uuid4()
    redis = AsyncMock()
    settings = Settings(minio_media_bucket="wished-media")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_redis] = lambda: redis

    async def fake_upload(db, current_user, requested_id, file, current_settings, current_redis):
        assert current_user is user
        assert requested_id == wishlist_id
        assert file.filename == "cover.jpg"
        assert current_settings is settings
        assert current_redis is redis
        return _wishlist(owner_user_id=user.id, wishlist_id=wishlist_id)

    monkeypatch.setattr("app.api.v1.wishlists.router.upload_wishlist_cover", fake_upload)

    response = TestClient(app).post(
        f"/api/v1/wishlists/{wishlist_id}/cover",
        files={"file": ("cover.jpg", b"\xff\xd8\xff", "image/jpeg")},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_wishlist_cover_rejects_oversized_file(monkeypatch) -> None:
    from app.modules.wishlists.service import upload_wishlist_cover

    monkeypatch.setattr(
        "app.modules.wishlists.service._get_owned_wishlist",
        AsyncMock(return_value=SimpleNamespace()),
    )
    redis = _rate_limit_redis()
    file = UploadFile(
        filename="cover.jpg",
        file=BytesIO(b"\xff\xd8\xff" + b"x" * (5 * 1024 * 1024)),
        headers={"content-type": "image/jpeg"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await upload_wishlist_cover(
            AsyncMock(),
            _user(),
            uuid4(),
            file,
            Settings(),
            redis,
        )

    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_wishlist_cover_rejects_disallowed_file_type(monkeypatch) -> None:
    from app.modules.wishlists.service import upload_wishlist_cover

    monkeypatch.setattr(
        "app.modules.wishlists.service._get_owned_wishlist",
        AsyncMock(return_value=SimpleNamespace()),
    )
    file = UploadFile(
        filename="cover.svg",
        file=BytesIO(b"<svg></svg>"),
        headers={"content-type": "image/svg+xml"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await upload_wishlist_cover(
            AsyncMock(),
            _user(),
            uuid4(),
            file,
            Settings(),
            _rate_limit_redis(),
        )

    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_delete_wishlist_removes_all_image_variants(monkeypatch) -> None:
    from app.modules.wishlists.service import delete_wishlist

    wishlist = SimpleNamespace(
        cover_image_bucket=None,
        cover_image_object_name=None,
        cover_image_thumbnail_object_name=None,
        cover_image_medium_object_name=None,
    )
    image = SimpleNamespace(
        bucket="wished-media",
        object_name="full",
        thumbnail_object_name="thumbnail",
        medium_object_name="medium",
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [SimpleNamespace(images=[image])]
    db = AsyncMock()
    db.execute.return_value = result
    deleted_objects: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "app.modules.wishlists.service._get_owned_wishlist",
        AsyncMock(return_value=wishlist),
    )
    monkeypatch.setattr(
        "app.modules.wishlists.service.delete_object",
        lambda bucket, object_name: deleted_objects.append((bucket, object_name)),
    )

    await delete_wishlist(db, _user(), uuid4())

    assert deleted_objects == [
        ("wished-media", "full"),
        ("wished-media", "thumbnail"),
        ("wished-media", "medium"),
    ]


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

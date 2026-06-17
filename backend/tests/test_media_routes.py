from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.core.config import Settings, get_settings
from app.main import create_app


def test_upload_wish_image_accepts_image_file(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wish_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_settings] = _settings

    async def fake_upload_wish_image(db, current_user, requested_wish_id, file, settings):
        assert current_user is user
        assert requested_wish_id == wish_id
        assert file.content_type == "image/png"
        assert settings.minio_media_bucket == "wished-media"
        return _image(wish_id=wish_id, content_type=file.content_type)

    monkeypatch.setattr("app.api.v1.media.router.upload_wish_image", fake_upload_wish_image)

    response = TestClient(app).post(
        f"/wishes/{wish_id}/images",
        files={"file": ("image.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["wish_id"] == str(wish_id)
    assert response.json()["content_type"] == "image/png"


def test_delete_wish_image_returns_no_content(monkeypatch) -> None:
    app = create_app()
    user = _user()
    wish_id = uuid4()
    image_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()

    async def fake_delete_wish_image(db, current_user, requested_wish_id, requested_image_id):
        assert current_user is user
        assert requested_wish_id == wish_id
        assert requested_image_id == image_id

    monkeypatch.setattr("app.api.v1.media.router.delete_wish_image", fake_delete_wish_image)

    response = TestClient(app).delete(f"/wishes/{wish_id}/images/{image_id}")

    assert response.status_code == 204


def test_upload_wish_image_rejects_missing_file() -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_settings] = _settings

    response = TestClient(app).post(f"/wishes/{uuid4()}/images")

    assert response.status_code == 422


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def _settings() -> Settings:
    return Settings(
        minio_media_bucket="wished-media",
        minio_public_endpoint="http://localhost:9000",
    )


def _image(wish_id, content_type: str) -> dict[str, object]:
    return {
        "id": uuid4(),
        "wish_id": wish_id,
        "url": "http://localhost:9000/wished-media/wishes/image.png",
        "file_name": "image.png",
        "content_type": content_type,
        "size_bytes": 11,
        "created_at": datetime(2026, 6, 14, 10, 0, tzinfo=UTC),
    }

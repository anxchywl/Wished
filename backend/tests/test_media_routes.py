"""media route tests"""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

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

def _user():
    return SimpleNamespace(id=uuid4())


def _settings():
    return Settings(
        minio_media_bucket="wished-media",
        minio_public_endpoint="http://localhost:9000",
    )


def _image(wish_id, content_type: str = "image/webp") -> dict:
    image_id = uuid4()
    return {
        "id": image_id,
        "wish_id": wish_id,
        "url": f"http://localhost:9000/wished-media/wishes/{wish_id}/{image_id}?X-Amz-Signature=abc",
        "thumbnail_url": f"http://localhost:9000/wished-media/wishes/{wish_id}/{image_id}-t?X-Amz-Signature=abc",
        "medium_url": f"http://localhost:9000/wished-media/wishes/{wish_id}/{image_id}-m?X-Amz-Signature=abc",
        "file_name": f"{image_id}.webp",
        "content_type": content_type,
        "size_bytes": 1024,
        "status": "ready",
        "created_at": datetime(2026, 6, 19, 10, 0, tzinfo=UTC),
    }


def _fake_redis():
    r = AsyncMock()
    # pipeline that returns [1, True, 1, True] (below rate limits)
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, True, 1, True])
    r.pipeline = MagicMock(return_value=pipe)
    return r


def _make_app(monkeypatch, fake_service=None):
    app = create_app()
    user = _user()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[get_redis] = _fake_redis

    if fake_service:
        for name, fn in fake_service.items():
            monkeypatch.setattr(f"app.api.v1.media.router.{name}", fn)

    return app, user


# ---------------------------------------------------------------------------
# upload tests
# ---------------------------------------------------------------------------

def test_upload_wish_image_accepts_valid_jpeg(monkeypatch) -> None:
    wish_id = uuid4()

    async def fake_upload(db, current_user, wid, file, settings, redis):
        assert wid == wish_id
        assert file.content_type == "image/jpeg"
        return _image(wish_id, "image/webp")

    app, _ = _make_app(monkeypatch, {"upload_wish_image": fake_upload})
    resp = TestClient(app).post(
        f"/api/v1/wishes/{wish_id}/images",
        files={"file": ("photo.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["content_type"] == "image/webp"
    assert body["thumbnail_url"] is not None
    assert body["medium_url"] is not None
    assert body["status"] == "ready"


def test_upload_wish_image_accepts_valid_png(monkeypatch) -> None:
    wish_id = uuid4()

    async def fake_upload(db, current_user, wid, file, settings, redis):
        return _image(wish_id, "image/webp")

    app, _ = _make_app(monkeypatch, {"upload_wish_image": fake_upload})
    resp = TestClient(app).post(
        f"/api/v1/wishes/{wish_id}/images",
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")},
    )
    assert resp.status_code == 201


def test_upload_wish_image_rejects_missing_file() -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[get_redis] = _fake_redis

    resp = TestClient(app).post(f"/api/v1/wishes/{uuid4()}/images")
    assert resp.status_code == 422


def test_delete_wish_image_returns_no_content(monkeypatch) -> None:
    wish_id = uuid4()
    image_id = uuid4()

    async def fake_delete(db, current_user, wid, iid, redis=None):
        assert wid == wish_id
        assert iid == image_id

    app, _ = _make_app(monkeypatch, {"delete_wish_image": fake_delete})
    resp = TestClient(app).delete(f"/api/v1/wishes/{wish_id}/images/{image_id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# validation-layer tests (calling service directly with real validation)
# ---------------------------------------------------------------------------

def _minimal_jpeg() -> bytes:
    """minimal valid JPEG: SOI + APP0 marker"""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 16


def _minimal_png() -> bytes:
    """PNG signature only (enough for magic byte check)"""
    return b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a" + b"\x00" * 16


def _minimal_webp() -> bytes:
    """minimal WEBP container header"""
    return b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 4


def test_validate_image_upload_rejects_svg() -> None:
    from app.modules.media.validation import validate_image_upload
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload("image.svg", "image/svg+xml", b"<svg></svg>")
    assert exc_info.value.status_code == 415


def test_validate_image_upload_rejects_disallowed_extension() -> None:
    from app.modules.media.validation import validate_image_upload
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload("shell.php", "image/jpeg", _minimal_jpeg())
    assert exc_info.value.status_code == 415


def test_validate_image_upload_rejects_double_extension() -> None:
    from app.modules.media.validation import validate_image_upload
    from fastapi import HTTPException

    # e.g. malware.php.jpg — extension is "jpg" but content is not JPEG
    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload("malware.php.jpg", "image/jpeg", b"<?php system($_GET['cmd']); ?>")
    # magic bytes fail — file content is not a JPEG
    assert exc_info.value.status_code == 415


def test_validate_image_upload_rejects_fake_mime_type() -> None:
    from app.modules.media.validation import validate_image_upload
    from fastapi import HTTPException

    # PNG bytes but declared as JPEG
    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload("image.jpeg", "image/jpeg", _minimal_png())
    assert exc_info.value.status_code == 415


def test_validate_image_upload_rejects_renamed_executable() -> None:
    from app.modules.media.validation import validate_image_upload
    from fastapi import HTTPException

    # ELF binary renamed to .jpg
    elf_magic = b"\x7fELF" + b"\x00" * 12
    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload("virus.jpg", "image/jpeg", elf_magic)
    assert exc_info.value.status_code == 415


def test_validate_image_upload_accepts_real_jpeg() -> None:
    from app.modules.media.validation import validate_image_upload

    validate_image_upload("photo.jpg", "image/jpeg", _minimal_jpeg())


def test_validate_image_upload_accepts_real_png() -> None:
    from app.modules.media.validation import validate_image_upload

    validate_image_upload("photo.png", "image/png", _minimal_png())


def test_validate_image_upload_accepts_real_webp() -> None:
    from app.modules.media.validation import validate_image_upload

    validate_image_upload("photo.webp", "image/webp", _minimal_webp())


def test_validate_image_upload_accepts_jpeg_extension() -> None:
    from app.modules.media.validation import validate_image_upload

    validate_image_upload("photo.jpeg", "image/jpeg", _minimal_jpeg())


# ---------------------------------------------------------------------------
# rate limiting tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limit_raises_429_when_per_minute_exceeded() -> None:
    from app.modules.media.rate_limit import check_upload_rate_limit
    from fastapi import HTTPException

    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    # per-minute counter exceeds limit
    pipe.execute = AsyncMock(return_value=[21, True, 5, True])
    redis.pipeline = MagicMock(return_value=pipe)

    with pytest.raises(HTTPException) as exc_info:
        await check_upload_rate_limit(redis, uuid4(), 20, 100)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_raises_429_when_per_hour_exceeded() -> None:
    from app.modules.media.rate_limit import check_upload_rate_limit
    from fastapi import HTTPException

    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    # hourly counter exceeds limit
    pipe.execute = AsyncMock(return_value=[1, True, 101, True])
    redis.pipeline = MagicMock(return_value=pipe)

    with pytest.raises(HTTPException) as exc_info:
        await check_upload_rate_limit(redis, uuid4(), 20, 100)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_passes_within_limits() -> None:
    from app.modules.media.rate_limit import check_upload_rate_limit

    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, True, 1, True])
    redis.pipeline = MagicMock(return_value=pipe)

    # should not raise
    await check_upload_rate_limit(redis, uuid4(), 20, 100)

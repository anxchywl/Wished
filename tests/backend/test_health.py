from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.main import create_app


def test_health_endpoint_returns_ok_when_dependencies_are_available(
    monkeypatch,
) -> None:
    app = create_app()
    db = AsyncMock()
    redis = AsyncMock()
    redis.ping.return_value = True
    minio = MagicMock()
    minio.list_buckets.return_value = []

    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_redis] = lambda: redis
    monkeypatch.setattr("app.api.v1.health.router.get_minio_client", lambda: minio)

    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": {"status": "ok"},
        "redis": {"status": "ok"},
        "minio": {"status": "ok"},
    }


def test_health_endpoint_returns_503_when_minio_is_unavailable(monkeypatch) -> None:
    app = create_app()
    db = AsyncMock()
    redis = AsyncMock()
    redis.ping.return_value = True
    minio = MagicMock()
    minio.list_buckets.side_effect = RuntimeError("unavailable")

    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_redis] = lambda: redis
    monkeypatch.setattr("app.api.v1.health.router.get_minio_client", lambda: minio)

    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["minio"] == {"status": "error"}

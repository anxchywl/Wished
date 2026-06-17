from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_response_shape() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json().keys() == {"status", "database", "redis"}

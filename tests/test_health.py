"""HTTP health endpoint contract."""

from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_returns_not_found() -> None:
    with TestClient(app) as client:
        response = client.get("/missing")

    assert response.status_code == 404

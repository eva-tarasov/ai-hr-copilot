"""HTTP health endpoint contract."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_returns_not_found(client: TestClient) -> None:
    response = client.get("/missing")

    assert response.status_code == 404

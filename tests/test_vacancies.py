"""S01 API behavior with a fresh temporary SQLite database per test."""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


def create_vacancy(client: TestClient, title: str = "Engineer") -> dict:
    response = client.post(
        "/vacancies", json={"title": title, "description": "Build reliable systems"}
    )
    assert response.status_code == 201
    return response.json()


def test_vacancy_create_list_detail_and_update(client: TestClient) -> None:
    assert client.get("/vacancies").json() == []

    response = client.post(
        "/vacancies", json={"title": "  Engineer  ", "description": "  Build systems  "}
    )
    assert response.status_code == 201
    vacancy = response.json()
    assert vacancy["title"] == "Engineer"
    assert vacancy["description"] == "Build systems"
    assert vacancy["id"] > 0
    assert vacancy["created_at"]
    assert vacancy["updated_at"]

    vacancy_id = vacancy["id"]
    assert client.get("/vacancies").json() == [vacancy]
    assert client.get(f"/vacancies/{vacancy_id}").json() == vacancy

    changed = client.patch(
        f"/vacancies/{vacancy_id}", json={"description": "Maintain systems"}
    )
    assert changed.status_code == 200
    assert changed.json()["title"] == "Engineer"
    assert changed.json()["description"] == "Maintain systems"
    assert client.get(f"/vacancies/{vacancy_id}").json() == changed.json()


def test_criteria_create_order_update_and_delete(client: TestClient) -> None:
    vacancy_id = create_vacancy(client)["id"]
    required = client.post(
        f"/vacancies/{vacancy_id}/criteria",
        json={"description": "  Python  ", "priority": "required"},
    )
    preferred = client.post(
        f"/vacancies/{vacancy_id}/criteria",
        json={"description": "SQL", "priority": "preferred", "active": False},
    )
    assert required.status_code == preferred.status_code == 201
    first = required.json()
    second = preferred.json()
    assert first["description"] == "Python"
    assert first["priority"] == "required"
    assert first["active"] is True
    assert first["display_order"] == 0
    assert second["priority"] == "preferred"
    assert second["active"] is False
    assert second["display_order"] == 1
    assert client.get(f"/vacancies/{vacancy_id}/criteria").json() == [first, second]

    changed = client.patch(
        f"/criteria/{first['id']}",
        json={"description": "Python 3", "priority": "preferred", "active": False, "display_order": 2},
    )
    assert changed.status_code == 200
    assert changed.json()["description"] == "Python 3"
    assert changed.json()["priority"] == "preferred"
    assert changed.json()["active"] is False
    assert changed.json()["display_order"] == 2
    assert client.get(f"/vacancies/{vacancy_id}/criteria").json() == [second, changed.json()]

    deleted = client.delete(f"/criteria/{second['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/vacancies/{vacancy_id}/criteria").json() == [changed.json()]


def test_missing_vacancy_and_criterion_return_404(client: TestClient) -> None:
    assert client.get("/vacancies/999").status_code == 404
    assert client.patch("/vacancies/999", json={"title": "Missing"}).status_code == 404
    assert client.get("/vacancies/999/criteria").status_code == 404
    assert (
        client.post(
            "/vacancies/999/criteria", json={"description": "Python", "priority": "required"}
        ).status_code
        == 404
    )
    assert client.patch("/criteria/999", json={"active": False}).status_code == 404
    assert client.delete("/criteria/999").status_code == 404


def test_invalid_vacancy_and_criterion_payloads_return_422(client: TestClient) -> None:
    for payload in (
        {"title": "   ", "description": "Description"},
        {"title": "Title", "description": "  "},
        {"title": "x" * 201, "description": "Description"},
    ):
        assert client.post("/vacancies", json=payload).status_code == 422

    vacancy_id = create_vacancy(client)["id"]
    for payload in ({}, {"title": "  "}, {"title": None}, {"description": None}):
        assert client.patch(f"/vacancies/{vacancy_id}", json=payload).status_code == 422

    for payload in (
        {"description": "  ", "priority": "required"},
        {"description": "x" * 501, "priority": "required"},
        {"description": "Python", "priority": "important"},
        {"description": "Python", "priority": "required", "display_order": -1},
    ):
        assert client.post(f"/vacancies/{vacancy_id}/criteria", json=payload).status_code == 422

    criterion = client.post(
        f"/vacancies/{vacancy_id}/criteria",
        json={"description": "Python", "priority": "required"},
    ).json()
    for payload in (
        {},
        {"description": "  "},
        {"priority": "important"},
        {"active": None},
        {"display_order": -1},
    ):
        assert client.patch(f"/criteria/{criterion['id']}", json=payload).status_code == 422


def test_criteria_are_isolated_between_vacancies(client: TestClient) -> None:
    first_id = create_vacancy(client, "First")["id"]
    second_id = create_vacancy(client, "Second")["id"]
    criterion = client.post(
        f"/vacancies/{first_id}/criteria",
        json={"description": "Python", "priority": "required"},
    ).json()

    assert client.get(f"/vacancies/{second_id}/criteria").json() == []
    moved = client.patch(f"/criteria/{criterion['id']}", json={"vacancy_id": second_id})
    assert moved.status_code == 422
    assert client.get(f"/vacancies/{first_id}/criteria").json() == [criterion]
    assert client.get(f"/vacancies/{second_id}/criteria").json() == []


def test_records_persist_across_app_restarts(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'nested' / 'persistent.sqlite3'}"
    with TestClient(create_app(database_url=database_url)) as first_client:
        vacancy_id = create_vacancy(first_client)["id"]
        created = first_client.post(
            f"/vacancies/{vacancy_id}/criteria",
            json={"description": "Python", "priority": "required"},
        )
        assert created.status_code == 201

    with TestClient(create_app(database_url=database_url)) as second_client:
        assert second_client.get(f"/vacancies/{vacancy_id}").status_code == 200
        assert second_client.get(f"/vacancies/{vacancy_id}/criteria").json() == [created.json()]

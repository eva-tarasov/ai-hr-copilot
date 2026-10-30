"""Archive and run-history API checks on isolated SQLite and synthetic documents."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, local
from time import monotonic, sleep
import sqlite3

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event

from backend.app.main import create_app
from backend.app.repositories.resumes import ArchiveDuringRunError, ResumeRepository
from backend.app.services.batch_analysis import BatchAnalysisService
from tests.test_resumes import pdf_bytes


def vacancy(client: TestClient, title: str) -> int:
    response = client.post("/vacancies", json={"title": title, "description": "Synthetic role"})
    assert response.status_code == 201
    return response.json()["id"]


def criterion(client: TestClient, vacancy_id: int) -> int:
    response = client.post(f"/vacancies/{vacancy_id}/criteria", json={
        "description": "Python", "priority": "required",
    })
    assert response.status_code == 201
    return response.json()["id"]


def upload(client: TestClient, vacancy_id: int, name: str, content: bytes) -> dict:
    response = client.post(f"/vacancies/{vacancy_id}/resumes", files=[
        ("files", (name, content, "application/pdf")),
    ])
    assert response.status_code == 200
    return response.json()["results"][0]


def run(client: TestClient, vacancy_id: int) -> dict:
    response = client.post(f"/vacancies/{vacancy_id}/analyses")
    assert response.status_code == 202
    run_id = response.json()["id"]
    deadline = monotonic() + 5
    while monotonic() < deadline:
        state = client.get(f"/analyses/{run_id}").json()
        if state["status"] in {"completed", "completed_with_errors", "failed", "interrupted"}:
            return state
        sleep(0.01)
    raise AssertionError("synthetic run did not finish")


def test_linked_resume_archives_without_losing_history_and_restores_to_new_run(
    client: TestClient,
) -> None:
    vacancy_id = vacancy(client, "Primary")
    criterion_id = criterion(client, vacancy_id)
    content = pdf_bytes("I have experience with Python.")
    first = upload(client, vacancy_id, "first.pdf", content)
    second = upload(client, vacancy_id, "second.pdf", pdf_bytes("I have experience with Python second."))
    old_run = run(client, vacancy_id)
    old_results = client.get(f"/analyses/{old_run['id']}/results").json()
    assert old_results["results"][0]["findings"][0]["evidence_quote"]

    archived = client.post(f"/resumes/{first['resume_id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert archived.json()["archived_at"]
    repeat = client.post(f"/resumes/{first['resume_id']}/archive")
    assert repeat.status_code == 200
    assert repeat.json()["archived_at"] == archived.json()["archived_at"]
    assert [item["id"] for item in client.get(f"/vacancies/{vacancy_id}/resumes").json()] == [second["resume_id"]]
    all_resumes = client.get(f"/vacancies/{vacancy_id}/resumes?include_archived=true").json()
    assert [item["archived"] for item in all_resumes] == [True, False]
    detail = client.get(f"/resumes/{first['resume_id']}").json()
    assert detail["archived"] is True
    assert detail["extracted_text"] == "I have experience with Python."
    duplicate = upload(client, vacancy_id, "again.pdf", content)
    assert duplicate["duplicate"] is True
    assert duplicate["archived"] is True
    assert duplicate["resume_id"] == first["resume_id"]
    assert len(client.get(f"/vacancies/{vacancy_id}/resumes?include_archived=true").json()) == 2

    next_run = run(client, vacancy_id)
    assert next_run["total"] == 1
    assert [item["resume_id"] for item in client.get(f"/analyses/{next_run['id']}/results").json()["results"]] == [second["resume_id"]]
    assert client.get(f"/analyses/{old_run['id']}/results").json() == old_results
    assert client.delete(f"/resumes/{first['resume_id']}").status_code == 409

    restored = client.post(f"/resumes/{first['resume_id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["archived"] is False
    assert restored.json()["archived_at"] is None
    assert client.post(f"/resumes/{first['resume_id']}/restore").status_code == 200
    final_run = run(client, vacancy_id)
    assert final_run["total"] == 2
    assert final_run["criterion_snapshot"][0]["id"] == criterion_id
    assert [item["resume_id"] for item in client.get(f"/analyses/{final_run['id']}/results").json()["results"]] == [
        first["resume_id"], second["resume_id"],
    ]
    assert client.get(f"/analyses/{old_run['id']}/results").json() == old_results


def test_archive_active_run_block_and_other_vacancy_independent(client: TestClient) -> None:
    first_vacancy = vacancy(client, "First")
    second_vacancy = vacancy(client, "Second")
    criterion(client, first_vacancy)
    first = upload(client, first_vacancy, "first.pdf", pdf_bytes("I have experience with Python."))
    second = upload(client, second_vacancy, "second.pdf", pdf_bytes("I have experience with Python."))
    with client.app.state.session_factory() as session:
        from backend.app.models import AnalysisRun
        session.add(AnalysisRun(
            vacancy_id=first_vacancy, criterion_snapshot_json=[], provider="fake", model=None,
            schema_version="test", prompt_version="test", status="pending",
        ))
        session.commit()
    blocked = client.post(f"/resumes/{first['resume_id']}/archive")
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "active_run_blocks_archive"}
    assert client.get(f"/resumes/{first['resume_id']}").json()["archived"] is False
    assert client.post(f"/resumes/{second['resume_id']}/archive").status_code == 200
    assert client.get(f"/vacancies/{second_vacancy}/resumes").json() == []
    assert len(client.get(f"/vacancies/{first_vacancy}/resumes").json()) == 1


@pytest.mark.parametrize("first_operation", ["archive", "run"])
def test_archive_and_run_creation_serialize_on_separate_sqlite_connections(
    client: TestClient, first_operation: str,
) -> None:
    vacancy_id = vacancy(client, f"Concurrent {first_operation}")
    criterion(client, vacancy_id)
    archived_candidate = upload(
        client, vacancy_id, "archive.pdf", pdf_bytes("I have experience with Python archive.")
    )
    remaining_candidate = upload(
        client, vacancy_id, "remaining.pdf", pdf_bytes("I have experience with Python remaining.")
    )
    previous_run = run(client, vacancy_id)
    previous_results = client.get(f"/analyses/{previous_run['id']}/results").json()

    factory = client.app.state.session_factory
    engine = factory.kw["bind"]
    thread_role = local()
    first_has_lock = Event()
    second_attempted_lock = Event()
    release_first = Event()

    def before_execute(connection, cursor, statement, parameters, context, executemany):
        if statement == "BEGIN IMMEDIATE" and getattr(thread_role, "value", None) == "second":
            second_attempted_lock.set()

    def after_execute(connection, cursor, statement, parameters, context, executemany):
        if statement == "BEGIN IMMEDIATE" and getattr(thread_role, "value", None) == "first":
            first_has_lock.set()
            if not release_first.wait(timeout=5):
                raise AssertionError("first transaction was not released")

    def operation(kind: str, role: str) -> tuple[int, int | str]:
        with factory() as session:
            thread_role.value = role
            try:
                connection_id = id(session.connection().connection.driver_connection)
                if kind == "run":
                    run_id = BatchAnalysisService(
                        session, client.app.state.analysis_provider
                    ).create(vacancy_id)
                    return connection_id, run_id
                try:
                    resume = ResumeRepository(session).archive(archived_candidate["resume_id"])
                except ArchiveDuringRunError:
                    return connection_id, "active_run_blocks_archive"
                assert resume is not None
                assert resume.archived is True
                return connection_id, "archived"
            finally:
                thread_role.value = None

    event.listen(engine, "before_cursor_execute", before_execute)
    event.listen(engine, "after_cursor_execute", after_execute)
    second_operation = "run" if first_operation == "archive" else "archive"
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(operation, first_operation, "first")
            assert first_has_lock.wait(timeout=5)
            second = workers.submit(operation, second_operation, "second")
            assert second_attempted_lock.wait(timeout=5)
            assert not second.done()  # SQLite cannot finish the second BEGIN while the first holds it.
            release_first.set()
            first_connection, first_result = first.result(timeout=5)
            second_connection, second_result = second.result(timeout=5)
    finally:
        release_first.set()
        event.remove(engine, "before_cursor_execute", before_execute)
        event.remove(engine, "after_cursor_execute", after_execute)

    assert first_connection != second_connection
    if first_operation == "archive":
        assert first_result == "archived"
        assert isinstance(second_result, int)
        assert [item["resume_id"] for item in client.get(
            f"/analyses/{second_result}/results"
        ).json()["results"]] == [remaining_candidate["resume_id"]]
        assert client.get(f"/resumes/{archived_candidate['resume_id']}").json()["archived"] is True
    else:
        assert isinstance(first_result, int)
        assert second_result == "active_run_blocks_archive"
        assert [item["resume_id"] for item in client.get(
            f"/analyses/{first_result}/results"
        ).json()["results"]] == [
            archived_candidate["resume_id"], remaining_candidate["resume_id"],
        ]
        blocked = client.post(f"/resumes/{archived_candidate['resume_id']}/archive")
        assert blocked.status_code == 409
        assert blocked.json() == {"detail": "active_run_blocks_archive"}
        assert client.get(f"/resumes/{archived_candidate['resume_id']}").json()["archived"] is False

    assert client.get(f"/analyses/{previous_run['id']}/results").json() == previous_results


def test_archive_missing_id_unlinked_delete_and_history_list_scoped(client: TestClient) -> None:
    first_vacancy = vacancy(client, "First")
    second_vacancy = vacancy(client, "Second")
    criterion(client, first_vacancy)
    criterion(client, second_vacancy)
    first = upload(client, first_vacancy, "first.pdf", pdf_bytes("I have experience with Python."))
    upload(client, second_vacancy, "second.pdf", pdf_bytes("I have experience with Python second."))
    assert client.post("/resumes/999/archive").status_code == 404
    assert client.post("/resumes/999/restore").status_code == 404
    assert client.get("/vacancies/999/analyses").status_code == 404
    assert client.get(f"/vacancies/{first_vacancy}/analyses").json() == []
    assert client.post(f"/resumes/{first['resume_id']}/archive").status_code == 200
    assert client.delete(f"/resumes/{first['resume_id']}").status_code == 204
    assert client.get(f"/resumes/{first['resume_id']}").status_code == 404

    upload(client, first_vacancy, "replacement.pdf", pdf_bytes("I have experience with Python replacement."))
    earlier = run(client, first_vacancy)
    later = run(client, first_vacancy)
    other = run(client, second_vacancy)
    history = client.get(f"/vacancies/{first_vacancy}/analyses").json()
    assert [item["id"] for item in history] == [later["id"], earlier["id"]]
    assert all(item["vacancy_id"] == first_vacancy for item in history)
    assert all(item["created_at"] and item["started_at"] and item["completed_at"] for item in history)
    assert [item["id"] for item in client.get(f"/vacancies/{second_vacancy}/analyses").json()] == [other["id"]]


def test_existing_sqlite_creates_archive_table_without_changing_resume(tmp_path: Path) -> None:
    path = tmp_path / "existing.sqlite3"
    db = f"sqlite:///{path}"
    files = tmp_path / "uploads"
    with TestClient(create_app(database_url=db, upload_dir=files)) as client:
        vacancy_id = vacancy(client, "Existing")
        resume = upload(client, vacancy_id, "old.pdf", pdf_bytes("I have experience with Python."))
    with sqlite3.connect(path) as connection:
        before = connection.execute("PRAGMA table_info(resumes)").fetchall()
        connection.execute("DROP TABLE resume_archives")
    with TestClient(create_app(database_url=db, upload_dir=files)) as client:
        assert client.get(f"/resumes/{resume['resume_id']}").json()["archived"] is False
        assert client.post(f"/resumes/{resume['resume_id']}/archive").status_code == 200
        assert client.get(f"/vacancies/{vacancy_id}/resumes").json() == []
    with sqlite3.connect(path) as connection:
        after = connection.execute("PRAGMA table_info(resumes)").fetchall()
        assert before == after

"""Offline coverage of review persistence and CSV safety."""
import csv
from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import inspect

from backend.app.core.database import create_db_engine
from backend.app.llm.fake import FakeProvider
from backend.app.main import create_app
from tests.test_resumes import pdf_bytes
from tests.test_batch_analysis import terminal
from ui.presentation import export_csv


def test_review_api_persists_and_is_isolated(tmp_path: Path):
    db = f"sqlite:///{tmp_path / 'reviews.sqlite3'}"
    uploads = tmp_path / "uploads"
    def app():
        return create_app(database_url=db, upload_dir=uploads, analysis_provider=FakeProvider())
    with TestClient(app()) as client:
        v = client.post("/vacancies", json={"title": "Synthetic", "description": "Demo"}).json()["id"]
        other = client.post("/vacancies", json={"title": "Other", "description": "Demo"}).json()["id"]
        resume = client.post(f"/vacancies/{v}/resumes", files={"files": ("a.pdf", pdf_bytes(), "application/pdf")}).json()["results"][0]["resume_id"]
        assert client.get("/vacancies/999/reviews").status_code == 404
        assert client.patch("/resumes/999/review", json={"reviewed": True, "note": None}).status_code == 404
        assert client.patch(f"/resumes/{resume}/review", json={"vacancy_id": other, "reviewed": True, "note": "wrong"}).status_code == 404
        assert client.patch(f"/resumes/{resume}/review", json={"reviewed": True, "note": "x" * 2001}).status_code == 422
        assert client.patch(f"/resumes/{resume}/review", json={"reviewed": "true", "note": None}).status_code == 422
        first = client.patch(f"/resumes/{resume}/review", json={"reviewed": True, "note": "Заметка"}).json()
        again = client.patch(f"/resumes/{resume}/review", json={"reviewed": False, "note": None}).json()
        assert first["id"] == again["id"] and again["note"] is None and not again["reviewed"]
        client.patch(f"/resumes/{resume}/review", json={"reviewed": True, "note": "Проверено"})
        assert len(client.get(f"/vacancies/{v}/reviews").json()) == 1
        assert client.get(f"/vacancies/{other}/reviews").json() == []
        assert client.post(f"/resumes/{resume}/archive").status_code == 200
        assert client.post(f"/resumes/{resume}/restore").status_code == 200
    with TestClient(app()) as reopened:
        saved = reopened.get(f"/vacancies/{v}/reviews").json()
        assert saved[0]["note"] == "Проверено" and saved[0]["reviewed"]


def test_existing_sqlite_gains_review_table(tmp_path: Path):
    db = f"sqlite:///{tmp_path / 'old.sqlite3'}"
    uploads = tmp_path / "uploads"
    with TestClient(create_app(database_url=db, upload_dir=uploads, analysis_provider=FakeProvider())):
        engine = create_db_engine(db)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE hr_reviews")
        engine.dispose()
    with TestClient(create_app(database_url=db, upload_dir=uploads, analysis_provider=FakeProvider())):
        engine = create_db_engine(db)
        assert "hr_reviews" in inspect(engine).get_table_names()
        engine.dispose()


def test_csv_snapshot_unicode_formula_and_failed_status():
    run = {"id": 4, "criterion_snapshot": [{"id": 1, "description": "=старый, \"критерий\"", "priority": "required"}]}
    results = [
        {"resume_id": 1, "filename": "=danger.pdf", "status": "completed", "findings": [{"criterion_id": 1, "status": "mentioned", "evidence_quote": "+текст\nстрока", "evidence_page": 1, "follow_up_question": "@уточнить"}]},
        {"resume_id": 2, "filename": "ошибка.pdf", "status": "failed", "findings": []},
        {"resume_id": 3, "filename": "прерван.pdf", "status": "interrupted", "findings": []},
    ]
    data = export_csv(9, run, results, {1: {"reviewed": True, "note": "\t=опасно, \"тест\""}})
    assert data.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(StringIO(data.decode("utf-8-sig"))))
    assert len(rows) == 3 and rows[0]["finding_status"] == "mentioned"
    assert rows[0]["criterion_description"] == "'=старый, \"критерий\""
    assert rows[0]["filename"] == "'=danger.pdf" and rows[0]["evidence_quote"] == "'+текст\nстрока"
    assert rows[0]["hr_note"] == "'\t=опасно, \"тест\"" and rows[0]["hr_reviewed"] == "true"
    assert [(r["document_status"], r["finding_status"]) for r in rows[1:]] == [("failed", ""), ("interrupted", "")]


@pytest.fixture
def review_client(tmp_path: Path):
    app = create_app(database_url=f"sqlite:///{tmp_path / 'snapshot.sqlite3'}",
                     upload_dir=tmp_path / "uploads", analysis_provider=FakeProvider())
    with TestClient(app) as client:
        yield client


def test_export_old_run_after_criterion_change(review_client):
    client = review_client
    vacancy = client.post("/vacancies", json={"title": "Role", "description": "Synthetic"}).json()["id"]
    criterion = client.post(f"/vacancies/{vacancy}/criteria", json={"description": "Python", "priority": "required"}).json()["id"]
    client.post(f"/vacancies/{vacancy}/resumes", files={"files": ("one.pdf", pdf_bytes("Experience: Python"), "application/pdf")})
    started = client.post(f"/vacancies/{vacancy}/analyses")
    assert started.status_code == 202
    run_id = started.json()["id"]
    assert terminal(client, run_id)["status"] == "completed"
    assert client.patch(f"/criteria/{criterion}", json={"description": "SQL"}).status_code == 200
    run = client.get(f"/analyses/{run_id}").json()
    results = client.get(f"/analyses/{run_id}/results").json()["results"]
    rows = list(csv.DictReader(StringIO(export_csv(vacancy, run, results, {}).decode("utf-8-sig"))))
    assert len(rows) == 1 and rows[0]["criterion_description"] == "Python"
    assert rows[0]["finding_status"] == "confirmed" and rows[0]["evidence_quote"] == "Experience: Python"


def test_review_note_is_not_sent_to_provider(tmp_path: Path):
    class RecordingFake(FakeProvider):
        def __init__(self):
            self.inputs = []

        async def analyze(self, text, criterion_snapshot):
            self.inputs.append((text, [item.description for item in criterion_snapshot]))
            return await super().analyze(text, criterion_snapshot)

    provider = RecordingFake()
    app = create_app(database_url=f"sqlite:///{tmp_path / 'privacy.sqlite3'}",
                     upload_dir=tmp_path / "uploads", analysis_provider=provider)
    with TestClient(app) as client:
        vacancy = client.post("/vacancies", json={"title": "Role", "description": "Synthetic"}).json()["id"]
        client.post(f"/vacancies/{vacancy}/criteria", json={"description": "Python", "priority": "required"})
        resume = client.post(f"/vacancies/{vacancy}/resumes", files={"files": ("one.pdf", pdf_bytes("Experience: Python"), "application/pdf")}).json()["results"][0]["resume_id"]
        client.patch(f"/resumes/{resume}/review", json={"reviewed": True, "note": "private synthetic review marker"})
        run = client.post(f"/vacancies/{vacancy}/analyses").json()["id"]
        assert terminal(client, run)["status"] == "completed"
        assert provider.inputs == [("Experience: Python", ["Python"])]

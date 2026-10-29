"""S04 integration checks with temporary SQLite and synthetic resumes only."""

import asyncio
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import create_db_engine, create_session_factory
from backend.app.llm.errors import ProviderError
from backend.app.llm.fake import FakeProvider
from backend.app.main import create_app
from backend.app.models import AnalysisRun, ResumeAnalysis
from backend.app.models.run_states import DOCUMENT_TRANSITIONS, RUN_TRANSITIONS, require_transition
from backend.app.repositories.analyses import AnalysisRepository
from tests.test_resumes import docx_bytes, pdf_bytes


def setup_vacancy(client: TestClient, *, criterion: str = "Python") -> tuple[int, int]:
    vacancy = client.post("/vacancies", json={"title": "Synthetic role", "description": "Test"}).json()["id"]
    response = client.post(
        f"/vacancies/{vacancy}/criteria",
        json={"description": criterion, "priority": "required"},
    )
    assert response.status_code == 201
    return vacancy, response.json()["id"]


def upload(client: TestClient, vacancy: int, files: list[tuple[str, bytes]]) -> None:
    response = client.post(
        f"/vacancies/{vacancy}/resumes",
        files=[("files", (name, contents, "application/octet-stream")) for name, contents in files],
    )
    assert response.status_code == 200


def terminal(client: TestClient, run_id: int) -> dict:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        response = client.get(f"/analyses/{run_id}")
        assert response.status_code == 200
        data = response.json()
        if data["status"] in {"completed", "completed_with_errors", "failed", "interrupted"}:
            return data
        sleep(0.01)
    raise AssertionError("analysis did not reach a terminal state")


class GateProvider(FakeProvider):
    def __init__(self) -> None:
        self.release = Event()
        self.active = 0
        self.maximum = 0

    async def analyze(self, text, criterion_snapshot):
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        try:
            while not self.release.is_set():
                await asyncio.sleep(0.01)
            return await super().analyze(text, criterion_snapshot)
        finally:
            self.active -= 1


class SelectiveProvider(FakeProvider):
    def __init__(self) -> None:
        self.attempts: dict[str, int] = {}

    async def analyze(self, text, criterion_snapshot):
        self.attempts[text] = self.attempts.get(text, 0) + 1
        if "transient" in text and self.attempts[text] < 3:
            raise ProviderError("timeout")
        if "refusal" in text:
            raise ProviderError("refusal")
        if "bad-output" in text:
            return {"findings": []}
        return await super().analyze(text, criterion_snapshot)


def test_three_resumes_persist_findings_and_snapshot_after_edit_delete(tmp_path: Path) -> None:
    db = f"sqlite:///{tmp_path / 'runs.sqlite3'}"
    with TestClient(create_app(database_url=db, upload_dir=tmp_path / "uploads")) as client:
        vacancy, criterion_id = setup_vacancy(client)
        upload(client, vacancy, [
            ("one.pdf", pdf_bytes("I have experience with Python.")),
            ("two.docx", docx_bytes("I have experience with Python.")),
            ("three.pdf", pdf_bytes("Python is mentioned.")),
        ])
        started = client.post(f"/vacancies/{vacancy}/analyses")
        assert started.status_code == 202
        run_id = started.json()["id"]
        done = terminal(client, run_id)
        assert done["status"] == "completed"
        assert (done["total"], done["completed"], done["failed"]) == (3, 3, 0)
        assert done["provider"] == "fake"
        assert done["schema_version"] and done["prompt_version"]
        assert done["started_at"] and done["completed_at"]
        results = client.get(f"/analyses/{run_id}/results").json()["results"]
        assert len(results) == 3
        assert all(item["status"] == "completed" for item in results)
        assert all(item["findings"][0]["criterion_id"] == criterion_id for item in results)
        assert results[0]["findings"][0]["evidence_page"] == 1
        assert results[1]["findings"][0]["evidence_page"] is None
        assert client.patch(
            f"/criteria/{criterion_id}",
            json={"description": "SQL", "priority": "preferred", "display_order": 42},
        ).status_code == 200
        assert client.delete(f"/criteria/{criterion_id}").status_code == 204
        frozen = client.get(f"/analyses/{run_id}").json()["criterion_snapshot"][0]
        assert (frozen["description"], frozen["priority"], frozen["display_order"]) == (
            "Python", "required", 0,
        )
        assert client.get(f"/analyses/{run_id}/results").json()["results"] == results
    with TestClient(create_app(database_url=db, upload_dir=tmp_path / "uploads")) as client:
        assert client.get(f"/analyses/{run_id}").json()["status"] == "completed"
        assert len(client.get(f"/analyses/{run_id}/results").json()["results"]) == 3


def test_nonblocking_submission_conflict_and_bounded_concurrency(tmp_path: Path) -> None:
    gate = GateProvider()
    with TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'runs.sqlite3'}",
                               upload_dir=tmp_path / "uploads", analysis_provider=gate,
                               max_concurrent_analyses=2)) as client:
        vacancy, _ = setup_vacancy(client)
        upload(client, vacancy, [
            (f"{i}.pdf", pdf_bytes(f"I have experience with Python {i}.")) for i in range(4)
        ])
        start = monotonic()
        response = client.post(f"/vacancies/{vacancy}/analyses")
        assert monotonic() - start < 1
        assert response.status_code == 202
        run_id = response.json()["id"]
        assert client.post(f"/vacancies/{vacancy}/analyses").status_code == 409
        deadline = monotonic() + 3
        while gate.maximum < 2 and monotonic() < deadline:
            sleep(0.01)
        assert gate.maximum == 2
        progress = client.get(f"/analyses/{run_id}").json()
        assert (progress["total"], progress["pending"], progress["running"], progress["completed"]) == (4, 2, 2, 0)
        gate.release.set()
        assert terminal(client, run_id)["status"] == "completed"
        assert gate.maximum == 2
        next_run = client.post(f"/vacancies/{vacancy}/analyses")
        assert next_run.status_code == 202
        assert terminal(client, next_run.json()["id"])["status"] == "completed"


def test_invalid_document_and_provider_errors_are_isolated(tmp_path: Path) -> None:
    provider = SelectiveProvider()
    with TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'runs.sqlite3'}",
                               upload_dir=tmp_path / "uploads", analysis_provider=provider)) as client:
        vacancy, _ = setup_vacancy(client)
        upload(client, vacancy, [
            ("good.pdf", pdf_bytes("I have experience with Python good.")),
            ("transient.pdf", pdf_bytes("I have experience with Python transient.")),
            ("refusal.pdf", pdf_bytes("I have experience with Python refusal.")),
            ("bad-output.docx", docx_bytes("I have experience with Python bad-output.")),
            ("broken.pdf", b"not a pdf"),
            ("unsupported.txt", b"synthetic non-resume"),
        ])
        response = client.post(f"/vacancies/{vacancy}/analyses")
        assert response.status_code == 202
        run_id = response.json()["id"]
        done = terminal(client, run_id)
        assert (done["status"], done["completed"], done["failed"]) == ("completed_with_errors", 2, 4)
        results = {item["filename"]: item for item in client.get(f"/analyses/{run_id}/results").json()["results"]}
        assert results["broken.pdf"]["error"] == "resume_not_ready"
        assert results["unsupported.txt"]["error"] == "resume_not_ready"
        assert results["refusal.pdf"]["error"] == "refusal"
        assert results["bad-output.docx"]["error"] == "missing_criterion_id"
        assert results["good.pdf"]["findings"]
        assert any("transient" in text and count == 3 for text, count in provider.attempts.items())
        assert any("refusal" in text and count == 1 for text, count in provider.attempts.items())
        assert len(provider.attempts) == 4


def test_preconditions_and_missing_runs(client: TestClient) -> None:
    assert client.post("/vacancies/999/analyses").status_code == 404
    assert client.get("/analyses/999").status_code == 404
    assert client.get("/analyses/999/results").status_code == 404
    vacancy, criterion_id = setup_vacancy(client)
    assert client.post(f"/vacancies/{vacancy}/analyses").status_code == 422
    upload(client, vacancy, [("bad.pdf", b"bad")])
    assert client.post(f"/vacancies/{vacancy}/analyses").json()["detail"] == "no_ready_resumes"
    upload(client, vacancy, [("good.pdf", pdf_bytes("I have experience with Python."))])
    assert client.patch(f"/criteria/{criterion_id}", json={"active": False}).status_code == 200
    assert client.post(f"/vacancies/{vacancy}/analyses").json()["detail"] == "no_active_criteria"
    assert client.patch(f"/criteria/{criterion_id}", json={"description": "age", "active": True}).status_code == 200
    assert client.post(f"/vacancies/{vacancy}/analyses").json()["detail"] == "prohibited_criterion"


def test_shutdown_marks_interrupted_and_restart_allows_retry(tmp_path: Path) -> None:
    db = f"sqlite:///{tmp_path / 'runs.sqlite3'}"
    gate = GateProvider()
    with TestClient(create_app(database_url=db, upload_dir=tmp_path / "uploads",
                               analysis_provider=gate)) as client:
        vacancy, _ = setup_vacancy(client)
        upload(client, vacancy, [("one.pdf", pdf_bytes("I have experience with Python."))])
        run_id = client.post(f"/vacancies/{vacancy}/analyses").json()["id"]
        deadline = monotonic() + 3
        while gate.maximum < 1 and monotonic() < deadline:
            sleep(0.01)
        assert gate.maximum == 1
    with TestClient(create_app(database_url=db, upload_dir=tmp_path / "uploads")) as client:
        state = client.get(f"/analyses/{run_id}").json()
        assert state["status"] == "interrupted"
        assert state["interrupted"] == 1
        assert client.get(f"/analyses/{run_id}/results").json()["results"][0]["error"] == "interrupted"
        retry = client.post(f"/vacancies/{vacancy}/analyses")
        assert retry.status_code == 202
        assert terminal(client, retry.json()["id"])["status"] == "completed"


def test_startup_recovers_abandoned_active_run(tmp_path: Path) -> None:
    db = f"sqlite:///{tmp_path / 'runs.sqlite3'}"
    with TestClient(create_app(database_url=db, upload_dir=tmp_path / "uploads")) as client:
        vacancy, _ = setup_vacancy(client)
        upload(client, vacancy, [("one.pdf", pdf_bytes("I have experience with Python."))])
        resume_id = client.get(f"/vacancies/{vacancy}/resumes").json()[0]["id"]
    engine = create_db_engine(db)
    with create_session_factory(engine)() as session:
        run = AnalysisRun(
            vacancy_id=vacancy, criterion_snapshot_json=[], provider="fake", model=None,
            schema_version="s03-v1", prompt_version="s03-v1", status="running",
        )
        session.add(run)
        session.flush()
        session.add(ResumeAnalysis(run_id=run.id, resume_id=resume_id, status="running"))
        session.commit()
        run_id = run.id
    engine.dispose()
    with TestClient(create_app(database_url=db, upload_dir=tmp_path / "uploads")) as client:
        state = client.get(f"/analyses/{run_id}").json()
        assert state["status"] == "interrupted"
        assert state["interrupted"] == 1
        assert client.post(f"/vacancies/{vacancy}/analyses").status_code == 202


def test_result_write_failure_is_isolated(tmp_path: Path, monkeypatch) -> None:
    original = AnalysisRepository.complete_document
    failed = False

    def fail_once(self, document_id, analysis):
        nonlocal failed
        if not failed:
            failed = True
            raise RuntimeError("synthetic storage failure with private data")
        return original(self, document_id, analysis)

    monkeypatch.setattr(AnalysisRepository, "complete_document", fail_once)
    with TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'runs.sqlite3'}",
                               upload_dir=tmp_path / "uploads")) as client:
        vacancy, _ = setup_vacancy(client)
        upload(client, vacancy, [
            ("one.pdf", pdf_bytes("I have experience with Python 1.")),
            ("two.pdf", pdf_bytes("I have experience with Python 2.")),
        ])
        run_id = client.post(f"/vacancies/{vacancy}/analyses").json()["id"]
        assert terminal(client, run_id)["status"] == "completed_with_errors"
        results = client.get(f"/analyses/{run_id}/results").json()["results"]
        assert sorted(item["status"] for item in results) == ["completed", "failed"]
        assert next(item for item in results if item["status"] == "failed")["error"] == "internal_error"
        assert "private data" not in str(results)


def test_concurrency_setting_must_be_positive(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CONCURRENT_ANALYSES", "0")
    with pytest.raises(ValueError, match="MAX_CONCURRENT_ANALYSES"):
        create_app()


def test_state_machine_rejects_terminal_and_skipped_transitions() -> None:
    require_transition(RUN_TRANSITIONS, "pending", "running")
    require_transition(RUN_TRANSITIONS, "running", "completed_with_errors")
    require_transition(DOCUMENT_TRANSITIONS, "pending", "failed")
    require_transition(DOCUMENT_TRANSITIONS, "running", "completed")
    for transitions, current, target in (
        (RUN_TRANSITIONS, "pending", "completed"),
        (RUN_TRANSITIONS, "completed", "running"),
        (DOCUMENT_TRANSITIONS, "completed", "failed"),
        (DOCUMENT_TRANSITIONS, "failed", "running"),
    ):
        with pytest.raises(ValueError, match="Invalid state transition"):
            require_transition(transitions, current, target)

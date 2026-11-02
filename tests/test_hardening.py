"""Regression tests for immutable inputs and local event-loop responsiveness."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event, get_ident

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event

from backend.app.core.database import create_db_engine, create_session_factory
from backend.app.llm.fake import FakeProvider
from backend.app.main import create_app
from backend.app.models import Resume
from backend.app.repositories.analyses import AnalysisRepository
from tests.test_batch_analysis import setup_vacancy, terminal, upload
from tests.test_resumes import pdf_bytes


def test_saved_input_is_used_after_resume_changes(tmp_path: Path, monkeypatch):
    db = f"sqlite:///{tmp_path / 'snapshot.sqlite3'}"
    entered, release = Event(), Event()
    original = AnalysisRepository.start_document

    def gate(self, document_id):
        entered.set()
        assert release.wait(5)
        return original(self, document_id)

    monkeypatch.setattr(AnalysisRepository, "start_document", gate)
    with TestClient(create_app(database_url=db, upload_dir=tmp_path / "files", analysis_provider=FakeProvider())) as client:
        vacancy, _ = setup_vacancy(client)
        upload(client, vacancy, [("one.pdf", pdf_bytes("Experience: Python"))])
        resume_id = client.get(f"/vacancies/{vacancy}/resumes").json()[0]["id"]
        run_id = client.post(f"/vacancies/{vacancy}/analyses").json()["id"]
        try:
            assert entered.wait(3)
            engine = create_db_engine(db)
            with create_session_factory(engine)() as session:
                resume = session.get(Resume, resume_id)
                resume.extracted_text = "Skills: Python"
                resume.source_pages = [{"page": 1, "text": "Skills: Python"}]
                session.commit()
            engine.dispose()
        finally:
            release.set()
        assert terminal(client, run_id)["status"] == "completed"
        result = client.get(f"/analyses/{run_id}/results").json()["results"][0]["findings"][0]
        assert (result["status"], result["evidence_quote"], result["evidence_page"]) == (
            "confirmed", "Experience: Python", 1,
        )
        second = client.post(f"/vacancies/{vacancy}/analyses").json()["id"]
        assert terminal(client, second)["status"] == "completed"
        assert client.get(f"/analyses/{second}/results").json()["results"][0]["findings"][0]["status"] == "mentioned"
        assert client.get(f"/analyses/{run_id}/results").json()["results"][0]["findings"][0] == result


def test_slow_db_does_not_block_http_or_share_session_thread(tmp_path: Path, monkeypatch):
    entered, release = Event(), Event()
    original = AnalysisRepository.start_document
    threads = []

    def slow(self, document_id):
        owner = get_ident()
        threads.append(owner)
        entered.set()
        assert release.wait(5)
        assert get_ident() == owner
        return original(self, document_id)

    monkeypatch.setattr(AnalysisRepository, "start_document", slow)
    with TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'latency.sqlite3'}",
                               upload_dir=tmp_path / "files", analysis_provider=FakeProvider())) as client:
        dispatcher = client.app.state.batch_dispatcher
        factory = dispatcher.session_factory
        owners = []

        def tracked_session():
            session = factory()
            owner = get_ident()
            owners.append((id(session), owner))

            @event.listens_for(session, "do_orm_execute")
            def same_thread(_state):
                assert get_ident() == owner

            @event.listens_for(session, "after_begin")
            def same_thread_at_begin(_session, _transaction, _connection):
                assert get_ident() == owner

            return session

        dispatcher.session_factory = tracked_session
        vacancy, _ = setup_vacancy(client)
        upload(client, vacancy, [("one.pdf", pdf_bytes("Experience: Python"))])
        run_id = client.post(f"/vacancies/{vacancy}/analyses").json()["id"]
        try:
            assert entered.wait(3)
            with ThreadPoolExecutor(max_workers=2) as pool:
                health = pool.submit(client.get, "/health")
                progress = pool.submit(client.get, f"/analyses/{run_id}")
                assert health.result(timeout=2).status_code == 200
                assert progress.result(timeout=2).status_code == 200
        finally:
            release.set()
        assert terminal(client, run_id)["status"] == "completed"
        assert threads and owners and threads[0] in {owner for _, owner in owners}


def test_existing_database_without_snapshot_table_preserves_history(tmp_path: Path):
    db = f"sqlite:///{tmp_path / 'legacy.sqlite3'}"
    def app():
        return create_app(database_url=db, upload_dir=tmp_path / "files", analysis_provider=FakeProvider())

    with TestClient(app()) as client:
        vacancy, _ = setup_vacancy(client)
        upload(client, vacancy, [("one.pdf", pdf_bytes("Experience: Python"))])
        first = client.post(f"/vacancies/{vacancy}/analyses").json()["id"]
        assert terminal(client, first)["status"] == "completed"
        history = client.get(f"/analyses/{first}/results").json()
    engine = create_db_engine(db)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE analysis_input_snapshots")
    engine.dispose()
    with TestClient(app()) as client:
        assert client.get(f"/analyses/{first}/results").json() == history
        second = client.post(f"/vacancies/{vacancy}/analyses").json()["id"]
        assert terminal(client, second)["status"] == "completed"


def test_missing_input_snapshot_fails_closed(tmp_path: Path, monkeypatch):
    db = f"sqlite:///{tmp_path / 'missing.sqlite3'}"
    entered, release = Event(), Event()
    original = AnalysisRepository.start_document

    def gate(self, document_id):
        entered.set()
        assert release.wait(5)
        return original(self, document_id)

    monkeypatch.setattr(AnalysisRepository, "start_document", gate)
    with TestClient(create_app(database_url=db, upload_dir=tmp_path / "files", analysis_provider=FakeProvider())) as client:
        vacancy, _ = setup_vacancy(client)
        upload(client, vacancy, [("one.pdf", pdf_bytes("Experience: Python"))])
        run_id = client.post(f"/vacancies/{vacancy}/analyses").json()["id"]
        try:
            assert entered.wait(3)
            engine = create_db_engine(db)
            with engine.begin() as connection:
                connection.exec_driver_sql("DELETE FROM analysis_input_snapshots")
            engine.dispose()
        finally:
            release.set()
        assert terminal(client, run_id)["status"] == "failed"
        result = client.get(f"/analyses/{run_id}/results").json()["results"][0]
        assert result["error"] == "input_snapshot_missing" and result["findings"] == []


def test_shutdown_waits_for_inflight_db_before_interrupting(tmp_path: Path, monkeypatch):
    db = f"sqlite:///{tmp_path / 'shutdown.sqlite3'}"
    entered, release = Event(), Event()
    original = AnalysisRepository.start_document

    def gate(self, document_id):
        entered.set()
        assert release.wait(5)
        return original(self, document_id)

    monkeypatch.setattr(AnalysisRepository, "start_document", gate)
    def app():
        return create_app(database_url=db, upload_dir=tmp_path / "files", analysis_provider=FakeProvider())

    client = TestClient(app())
    client.__enter__()
    try:
        vacancy, _ = setup_vacancy(client)
        upload(client, vacancy, [("one.pdf", pdf_bytes("Experience: Python"))])
        run_id = client.post(f"/vacancies/{vacancy}/analyses").json()["id"]
        assert entered.wait(3)
        with ThreadPoolExecutor(max_workers=1) as pool:
            shutdown = pool.submit(client.__exit__, None, None, None)
            try:
                with pytest.raises(TimeoutError):
                    shutdown.result(timeout=0.2)
            finally:
                release.set()
            shutdown.result(timeout=5)
    finally:
        release.set()
    with TestClient(app()) as reopened:
        assert reopened.get(f"/analyses/{run_id}").json()["status"] == "interrupted"

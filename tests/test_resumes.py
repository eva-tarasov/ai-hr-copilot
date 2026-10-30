"""Synthetic PDF/DOCX upload tests with temporary storage and SQLite."""

from io import BytesIO
from pathlib import Path
from typing import Callable

import pymupdf
import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app.main import create_app
from backend.app.models import AnalysisRun, ResumeAnalysis
from backend.app.repositories.file_storage import CHUNK_SIZE, FileStorage, UploadTooLargeError
from backend.app.repositories.resumes import ResumeRepository


def pdf_bytes(text: str = "Synthetic candidate: Python experience") -> bytes:
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), text)
        return document.tobytes()


def docx_bytes(text: str = "Synthetic candidate: SQL experience") -> bytes:
    document = Document()
    document.add_paragraph(text)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def vacancy_id(client: TestClient, title: str = "Analyst") -> int:
    response = client.post("/vacancies", json={"title": title, "description": "Synthetic role"})
    assert response.status_code == 201
    return response.json()["id"]


def upload(client: TestClient, vacancy: int, files: list[tuple[str, bytes, str]]) -> list[dict]:
    parts = [("files", (name, content, mime)) for name, content, mime in files]
    response = client.post(f"/vacancies/{vacancy}/resumes", files=parts)
    assert response.status_code == 200
    return response.json()["results"]


def test_pdf_upload_preserves_page_text_and_safe_name(client: TestClient, tmp_path: Path) -> None:
    vacancy = vacancy_id(client)
    result = upload(client, vacancy, [("../../candidate.pdf", pdf_bytes(), "text/plain")])[0]
    assert result["status"] == "ready"
    assert result["duplicate"] is False
    assert result["filename"] == "candidate.pdf"
    assert len(result["sha256"]) == 64

    detail = client.get(f"/resumes/{result['resume_id']}")
    assert detail.status_code == 200
    assert detail.json()["extracted_text"] == "Synthetic candidate: Python experience"
    assert len(detail.json()["source_pages"]) == 1
    assert detail.json()["source_pages"][0]["page"] == 1
    assert detail.json()["source_pages"][0]["text"].strip() == (
        "Synthetic candidate: Python experience"
    )
    assert detail.json()["page_count"] == 1
    listed = client.get(f"/vacancies/{vacancy}/resumes").json()
    assert len(listed) == 1
    assert "extracted_text" not in listed[0]
    assert len(list((tmp_path / "uploads" / str(vacancy)).glob("*.pdf"))) == 1
    assert not (tmp_path / "candidate.pdf").exists()


def test_docx_upload_extracts_text(client: TestClient) -> None:
    vacancy = vacancy_id(client)
    result = upload(client, vacancy, [("synthetic.docx", docx_bytes(), "application/octet-stream")])[0]
    assert result["status"] == "ready"
    detail = client.get(f"/resumes/{result['resume_id']}").json()
    assert detail["extracted_text"] == "Synthetic candidate: SQL experience"
    assert detail["source_pages"] == []
    assert detail["file_type"] == "docx"


def test_mixed_batch_reports_each_file_without_stopping(client: TestClient) -> None:
    vacancy = vacancy_id(client)
    results = upload(
        client,
        vacancy,
        [
            ("one.pdf", pdf_bytes("Synthetic one"), "application/pdf"),
            ("bad.pdf", b"%PDF-1.7\nbroken", "application/pdf"),
            ("two.docx", docx_bytes("Synthetic two"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("unknown.txt", b"synthetic plain text", "text/plain"),
            ("legacy.doc", b"synthetic legacy data", "application/msword"),
            ("empty.pdf", b"", "application/pdf"),
        ],
    )
    assert [item["status"] for item in results] == [
        "ready", "parse_error", "ready", "unsupported", "unsupported", "parse_error"
    ]
    assert all(item["resume_id"] is not None for item in results)
    listed = client.get(f"/vacancies/{vacancy}/resumes").json()
    assert len(listed) == 6
    assert listed[1]["parse_error"] == "Could not parse PDF"
    assert listed[3]["parse_error"] == "Only PDF and DOCX files are supported"
    assert listed[4]["parse_error"] == "Only PDF and DOCX files are supported"
    assert listed[5]["parse_error"] == "File is empty"


def test_corrupt_docx_and_mismatched_content(client: TestClient) -> None:
    vacancy = vacancy_id(client)
    results = upload(
        client,
        vacancy,
        [
            ("broken.docx", b"PK\x03\x04broken", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("wrong.pdf", docx_bytes("Synthetic mismatch"), "application/pdf"),
        ],
    )
    assert [item["status"] for item in results] == ["parse_error", "unsupported"]
    assert results[0]["error"] == "Could not parse DOCX"
    assert results[1]["error"] == "File content does not match PDF extension"


def test_no_text_pdf_is_not_ready(client: TestClient) -> None:
    with pymupdf.open() as document:
        document.new_page()
        blank = document.tobytes()
    result = upload(client, vacancy_id(client), [("scan.pdf", blank, "application/pdf")])[0]
    assert result["status"] == "unsupported"
    assert "OCR" in result["error"]


def test_oversized_file_is_rejected_without_blocking_next_file(tmp_path: Path) -> None:
    good = pdf_bytes("Synthetic small")
    limit = len(good)
    with TestClient(
        create_app(
            database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}",
            upload_dir=tmp_path / "uploads",
            max_upload_bytes=limit,
        )
    ) as client:
        vacancy = vacancy_id(client)
        results = upload(
            client,
            vacancy,
            [
                ("large.pdf", good + b"extra", "application/pdf"),
                ("small.pdf", good, "application/pdf"),
            ],
        )
        assert [item["status"] for item in results] == ["rejected", "ready"]
        assert results[0]["resume_id"] is None
        assert "byte limit" in results[0]["error"]
        assert len(client.get(f"/vacancies/{vacancy}/resumes").json()) == 1
    assert len(list((tmp_path / "uploads" / "tmp").glob("*"))) == 0


def test_duplicate_is_reused_within_vacancy_but_not_across_vacancies(client: TestClient) -> None:
    first = vacancy_id(client, "First")
    second = vacancy_id(client, "Second")
    content = pdf_bytes("Synthetic duplicate")
    original = upload(client, first, [("first.pdf", content, "application/pdf")])[0]
    repeated = upload(client, first, [("again.pdf", content, "application/pdf")])[0]
    elsewhere = upload(client, second, [("second.pdf", content, "application/pdf")])[0]
    assert repeated["duplicate"] is True
    assert repeated["resume_id"] == original["resume_id"]
    assert elsewhere["duplicate"] is False
    assert elsewhere["resume_id"] != original["resume_id"]
    assert len(client.get(f"/vacancies/{first}/resumes").json()) == 1
    assert len(client.get(f"/vacancies/{second}/resumes").json()) == 1


@pytest.mark.parametrize(
    ("content_factory", "correct_extension", "wrong_extension"),
    [
        (pdf_bytes, "pdf", "txt"),
        (pdf_bytes, "pdf", "docx"),
        (docx_bytes, "docx", "txt"),
        (docx_bytes, "docx", "pdf"),
    ],
)
def test_corrected_extension_replaces_unsupported_record(
    client: TestClient,
    tmp_path: Path,
    content_factory: Callable[[str], bytes],
    correct_extension: str,
    wrong_extension: str,
) -> None:
    vacancy = vacancy_id(client)
    content = content_factory("Synthetic corrected extension")
    wrong = upload(client, vacancy, [(f"candidate.{wrong_extension}", content, "application/octet-stream")])[0]
    assert wrong["status"] == "unsupported"

    corrected = upload(client, vacancy, [(f"candidate.{correct_extension}", content, "application/octet-stream")])[0]
    assert corrected["status"] == "ready"
    assert corrected["duplicate"] is False
    assert corrected["resume_id"] == wrong["resume_id"]
    assert corrected["sha256"] == wrong["sha256"]

    repeated = upload(client, vacancy, [(f"again.{correct_extension}", content, "application/octet-stream")])[0]
    assert repeated["status"] == "ready"
    assert repeated["duplicate"] is True
    assert repeated["resume_id"] == corrected["resume_id"]
    listed = client.get(f"/vacancies/{vacancy}/resumes").json()
    assert len(listed) == 1
    assert listed[0]["status"] == "ready"
    assert listed[0]["filename"] == f"candidate.{correct_extension}"
    assert listed[0]["file_type"] == correct_extension
    detail = client.get(f"/resumes/{corrected['resume_id']}").json()
    assert detail["extracted_text"] == "Synthetic corrected extension"
    assert len(list((tmp_path / "uploads" / str(vacancy)).iterdir())) == 1
    assert list((tmp_path / "uploads" / "tmp").iterdir()) == []


@pytest.mark.parametrize(
    ("content_factory", "correct_extension", "wrong_extension"),
    [
        (pdf_bytes, "pdf", "txt"),
        (pdf_bytes, "pdf", "docx"),
        (docx_bytes, "docx", "txt"),
        (docx_bytes, "docx", "pdf"),
    ],
)
def test_wrong_extension_after_ready_does_not_return_false_ready(
    client: TestClient,
    tmp_path: Path,
    content_factory: Callable[[str], bytes],
    correct_extension: str,
    wrong_extension: str,
) -> None:
    vacancy = vacancy_id(client)
    content = content_factory("Synthetic correct first")
    original = upload(client, vacancy, [(f"candidate.{correct_extension}", content, "application/octet-stream")])[0]
    wrong = upload(client, vacancy, [(f"candidate.{wrong_extension}", content, "application/octet-stream")])[0]
    assert wrong["status"] == "unsupported"
    assert wrong["duplicate"] is False
    assert wrong["resume_id"] is None
    assert wrong["sha256"] == original["sha256"]
    listed = client.get(f"/vacancies/{vacancy}/resumes").json()
    assert len(listed) == 1
    assert listed[0]["status"] == "ready"
    assert listed[0]["id"] == original["resume_id"]
    assert len(list((tmp_path / "uploads" / str(vacancy)).iterdir())) == 1
    assert list((tmp_path / "uploads" / "tmp").iterdir()) == []


@pytest.mark.parametrize("wrong_extension", ["txt", "docx"])
def test_database_failure_while_correcting_extension_keeps_original_record_and_files(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrong_extension: str
) -> None:
    vacancy = vacancy_id(client)
    content = pdf_bytes("Synthetic retry after database failure")
    original = upload(client, vacancy, [(f"candidate.{wrong_extension}", content, "application/octet-stream")])[0]
    files_before = list((tmp_path / "uploads" / str(vacancy)).glob("*"))

    def fail_commit(self: Session) -> None:
        raise OperationalError("UPDATE resumes", {}, Exception("synthetic SQLite failure"))

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        failed = upload(client, vacancy, [("candidate.pdf", content, "application/pdf")])[0]
    assert failed["status"] == "rejected"
    assert client.get(f"/resumes/{original['resume_id']}").json()["status"] == "unsupported"
    assert list((tmp_path / "uploads" / str(vacancy)).glob("*")) == files_before
    assert list((tmp_path / "uploads" / "tmp").iterdir()) == []

    retried = upload(client, vacancy, [("candidate.pdf", content, "application/pdf")])[0]
    assert retried["status"] == "ready"
    assert retried["resume_id"] == original["resume_id"]
    assert len(list((tmp_path / "uploads" / str(vacancy)).iterdir())) == 1


def test_file_failure_while_correcting_extension_keeps_original_record(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vacancy = vacancy_id(client)
    content = pdf_bytes("Synthetic retry after file failure")
    original = upload(client, vacancy, [("candidate.txt", content, "text/plain")])[0]

    def fail_promote(*args: object, **kwargs: object) -> None:
        raise OSError("synthetic storage failure")

    with monkeypatch.context() as patch:
        patch.setattr(FileStorage, "promote", fail_promote)
        failed = upload(client, vacancy, [("candidate.pdf", content, "application/pdf")])[0]
    assert failed["status"] == "rejected"
    assert client.get(f"/resumes/{original['resume_id']}").json()["status"] == "unsupported"
    assert list((tmp_path / "uploads" / str(vacancy)).glob("*")) == []
    assert list((tmp_path / "uploads" / "tmp").iterdir()) == []


def test_missing_vacancy_resume_and_file_return_404_or_422(client: TestClient) -> None:
    response = client.post(
        "/vacancies/999/resumes",
        files=[("files", ("synthetic.pdf", pdf_bytes(), "application/pdf"))],
    )
    assert response.status_code == 404
    assert client.get("/vacancies/999/resumes").status_code == 404
    assert client.get("/resumes/999").status_code == 404
    assert client.post(f"/vacancies/{vacancy_id(client)}/resumes").status_code == 422


def test_uploads_persist_after_app_restart(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.sqlite3'}"
    upload_dir = tmp_path / "uploads"
    with TestClient(create_app(database_url=database_url, upload_dir=upload_dir)) as first_client:
        vacancy = vacancy_id(first_client)
        result = upload(first_client, vacancy, [("synthetic.pdf", pdf_bytes(), "application/pdf")])[0]

    with TestClient(create_app(database_url=database_url, upload_dir=upload_dir)) as second_client:
        detail = second_client.get(f"/resumes/{result['resume_id']}")
        assert detail.status_code == 200
        assert detail.json()["extracted_text"] == "Synthetic candidate: Python experience"
        assert len(second_client.get(f"/vacancies/{vacancy}/resumes").json()) == 1
    assert len(list((upload_dir / str(vacancy)).glob("*.pdf"))) == 1


def test_failed_database_write_cleans_up_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vacancy = vacancy_id(client)

    def fail_create(*args: object, **kwargs: object) -> None:
        raise OSError("synthetic database failure")

    monkeypatch.setattr(ResumeRepository, "create", fail_create)
    result = upload(client, vacancy, [("synthetic.pdf", pdf_bytes(), "application/pdf")])[0]
    assert result["status"] == "rejected"
    assert result["resume_id"] is None
    assert client.get(f"/vacancies/{vacancy}/resumes").json() == []
    assert list((tmp_path / "uploads" / str(vacancy)).iterdir()) == []


def test_failed_file_promotion_leaves_no_database_record(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vacancy = vacancy_id(client)

    def fail_promote(*args: object, **kwargs: object) -> None:
        raise OSError("synthetic storage failure")

    monkeypatch.setattr(FileStorage, "promote", fail_promote)
    result = upload(client, vacancy, [("synthetic.pdf", pdf_bytes(), "application/pdf")])[0]
    assert result["status"] == "rejected"
    assert client.get(f"/vacancies/{vacancy}/resumes").json() == []
    assert list((tmp_path / "uploads" / "tmp").iterdir()) == []


def test_storage_reads_in_chunks_and_stops_at_limit(tmp_path: Path) -> None:
    class TrackingStream(BytesIO):
        read_sizes: list[int]

        def __init__(self, content: bytes) -> None:
            super().__init__(content)
            self.read_sizes = []

        def read(self, size: int = -1) -> bytes:
            self.read_sizes.append(size)
            return super().read(size)

    stream = TrackingStream(b"x" * (CHUNK_SIZE * 3))
    storage = FileStorage(tmp_path / "uploads")
    with pytest.raises(UploadTooLargeError):
        storage.stage(stream, max_bytes=CHUNK_SIZE // 2)
    assert stream.read_sizes == [CHUNK_SIZE]
    assert list((tmp_path / "uploads" / "tmp").iterdir()) == []


def test_multipart_parser_rejects_oversize_before_service_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_stage(*args: object, **kwargs: object) -> None:
        raise AssertionError("Service must not read an oversized multipart part")

    monkeypatch.setattr(FileStorage, "stage", fail_stage)
    with TestClient(
        create_app(
            database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}",
            upload_dir=tmp_path / "uploads",
            max_upload_bytes=32,
        )
    ) as client:
        vacancy = vacancy_id(client)
        result = upload(client, vacancy, [("large.pdf", b"x" * (CHUNK_SIZE * 3), "application/pdf")])[0]
        assert result["status"] == "rejected"
        assert result["error"] == "File exceeds 32 byte limit"
        assert client.get(f"/vacancies/{vacancy}/resumes").json() == []


def test_batch_file_count_is_bounded(client: TestClient) -> None:
    vacancy = vacancy_id(client)
    parts = [
        ("files", (f"synthetic-{index}.txt", f"content-{index}".encode(), "text/plain"))
        for index in range(21)
    ]
    response = client.post(f"/vacancies/{vacancy}/resumes", files=parts)
    assert response.status_code == 400
    assert client.get(f"/vacancies/{vacancy}/resumes").json() == []


def test_upload_is_documented_as_multipart(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"]["/vacancies/{vacancy_id}/resumes"]["post"]
    files = operation["requestBody"]["content"]["multipart/form-data"]["schema"]["properties"]["files"]
    assert files["type"] == "array"
    assert files["items"]["format"] == "binary"


def test_delete_unused_resume_and_file_is_idempotently_not_found(
    client: TestClient, tmp_path: Path
) -> None:
    vacancy = vacancy_id(client)
    first, second = upload(client, vacancy, [
        ("first.pdf", pdf_bytes("Synthetic first"), "application/pdf"),
        ("second.pdf", pdf_bytes("Synthetic second"), "application/pdf"),
    ])
    files = list((tmp_path / "uploads" / str(vacancy)).iterdir())
    assert len(files) == 2
    response = client.delete(f"/resumes/{first['resume_id']}")
    assert response.status_code == 204
    assert client.get(f"/resumes/{first['resume_id']}").status_code == 404
    assert client.delete(f"/resumes/{first['resume_id']}").status_code == 404
    assert len(list((tmp_path / "uploads" / str(vacancy)).iterdir())) == 1
    assert client.get(f"/resumes/{second['resume_id']}").status_code == 200
    assert list((tmp_path / "uploads" / "tmp").iterdir()) == []


@pytest.mark.parametrize("name,content", [
    ("unsupported.txt", b"synthetic unsupported"),
    ("broken.pdf", b"%PDF-1.7\nbroken"),
])
def test_delete_non_ready_resume(client: TestClient, tmp_path: Path,
                                 name: str, content: bytes) -> None:
    vacancy = vacancy_id(client)
    result = upload(client, vacancy, [(name, content, "application/octet-stream")])[0]
    assert result["status"] in ("unsupported", "parse_error")
    stored_before = list((tmp_path / "uploads" / str(vacancy)).glob("*"))
    assert client.delete(f"/resumes/{result['resume_id']}").status_code == 204
    assert client.get(f"/vacancies/{vacancy}/resumes").json() == []
    assert list((tmp_path / "uploads" / str(vacancy)).glob("*")) == []
    assert len(stored_before) == (1 if name.endswith(".pdf") else 0)


@pytest.mark.parametrize("run_status", ["pending", "completed"])
def test_delete_resume_in_any_saved_run_returns_409(
    client: TestClient, tmp_path: Path, run_status: str
) -> None:
    vacancy = vacancy_id(client)
    result = upload(client, vacancy, [("linked.pdf", pdf_bytes(), "application/pdf")])[0]
    with client.app.state.session_factory() as session:
        run = AnalysisRun(vacancy_id=vacancy, criterion_snapshot_json=[],
                          provider="fake", model=None, schema_version="test",
                          prompt_version="test", status=run_status)
        session.add(run)
        session.flush()
        session.add(ResumeAnalysis(run_id=run.id, resume_id=result["resume_id"]))
        session.commit()
    response = client.delete(f"/resumes/{result['resume_id']}")
    assert response.status_code == 409
    assert response.json() == {"detail": "resume_in_analysis"}
    assert client.get(f"/resumes/{result['resume_id']}").status_code == 200
    assert len(list((tmp_path / "uploads" / str(vacancy)).iterdir())) == 1


def test_delete_storage_failure_keeps_record_and_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vacancy = vacancy_id(client)
    result = upload(client, vacancy, [("keep.pdf", pdf_bytes(), "application/pdf")])[0]
    def fail_quarantine(*args: object) -> None:
        raise OSError("private storage path")
    monkeypatch.setattr(FileStorage, "quarantine", fail_quarantine)
    response = client.delete(f"/resumes/{result['resume_id']}")
    assert response.status_code == 503
    assert "private" not in response.text
    assert client.get(f"/resumes/{result['resume_id']}").status_code == 200
    assert len(list((tmp_path / "uploads" / str(vacancy)).iterdir())) == 1


def test_delete_fk_catches_run_created_after_initial_check(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vacancy = vacancy_id(client)
    result = upload(client, vacancy, [("linked.pdf", pdf_bytes(), "application/pdf")])[0]
    with client.app.state.session_factory() as session:
        run = AnalysisRun(vacancy_id=vacancy, criterion_snapshot_json=[],
                          provider="fake", model=None, schema_version="test",
                          prompt_version="test", status="completed")
        session.add(run)
        session.flush()
        session.add(ResumeAnalysis(run_id=run.id, resume_id=result["resume_id"]))
        session.commit()
    monkeypatch.setattr(ResumeRepository, "is_in_analysis", lambda *args: False)
    response = client.delete(f"/resumes/{result['resume_id']}")
    assert response.status_code == 409
    assert client.get(f"/resumes/{result['resume_id']}").status_code == 200
    assert len(list((tmp_path / "uploads" / str(vacancy)).iterdir())) == 1
    assert list((tmp_path / "uploads" / "tmp").iterdir()) == []


def test_delete_database_failure_restores_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vacancy = vacancy_id(client)
    result = upload(client, vacancy, [("keep.pdf", pdf_bytes(), "application/pdf")])[0]
    def fail_delete(*args: object) -> None:
        raise OperationalError("DELETE resumes", {}, Exception("private SQLite detail"))
    monkeypatch.setattr(ResumeRepository, "delete", fail_delete)
    response = client.delete(f"/resumes/{result['resume_id']}")
    assert response.status_code == 503
    assert "private" not in response.text
    assert client.get(f"/resumes/{result['resume_id']}").status_code == 200
    assert len(list((tmp_path / "uploads" / str(vacancy)).iterdir())) == 1
    assert list((tmp_path / "uploads" / "tmp").iterdir()) == []

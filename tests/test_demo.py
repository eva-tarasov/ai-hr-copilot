"""End-to-end S06a checks with synthetic bytes and an isolated SQLite database."""

from argparse import ArgumentTypeError
from collections import Counter
from pathlib import Path
from time import monotonic, sleep

from fastapi.testclient import TestClient
import pytest

from backend.app.main import create_app
from backend.app.parsing.documents import parse_document
from scripts.demo_fixtures import CRITERIA, SPECS, corpus, manifest
from scripts.demo_seed import TITLE, local_base_url, seed


def finished(client: TestClient, run_id: int) -> dict:
    deadline = monotonic() + 15
    while monotonic() < deadline:
        response = client.get(f"/analyses/{run_id}")
        assert response.status_code == 200
        run = response.json()
        if run["status"] in {"completed", "completed_with_errors", "failed", "interrupted"}:
            return run
        sleep(0.02)
    raise AssertionError("Demo run did not finish within 15 seconds")


def test_corpus_manifest_and_parsers(tmp_path: Path) -> None:
    documents = corpus()
    assert len(documents) == 18
    assert len({spec.filename for spec, _ in documents}) == 18
    assert len({data for _, data in documents}) == 18
    assert documents == corpus()
    assert Counter(spec.parse_status for spec, _ in documents) == {
        "ready": 15, "unsupported": 1, "parse_error": 2,
    }
    assert {spec.filename for spec, _ in documents if spec.parse_status == "ready" and spec.filename.endswith(".pdf")}
    assert {spec.filename for spec, _ in documents if spec.parse_status == "ready" and spec.filename.endswith(".docx")}

    published = manifest()
    assert [item["filename"] for item in published] == [spec.filename for spec, _ in documents]
    for spec, data in documents:
        path = tmp_path / spec.filename
        path.write_bytes(data)
        result = parse_document(path, path.suffix)
        assert result.status == spec.parse_status, spec.filename
        if spec.parse_status == "ready":
            assert result.text
            assert published[SPECS.index(spec)]["findings"] == dict(zip(
                (name for name, _ in CRITERIA), spec.findings, strict=True
            ))
            if path.suffix == ".pdf":
                assert len(result.source_pages) == len(spec.pages)
                assert [page["page"] for page in result.source_pages] == list(range(1, len(spec.pages) + 1))
            else:
                assert result.source_pages == []
        else:
            assert not result.text


def test_seed_full_fake_run_persistence_and_reanalysis(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'demo.sqlite3'}"
    upload_dir = tmp_path / "uploads"
    with TestClient(create_app(database_url=database_url, upload_dir=upload_dir)) as client:
        vacancy_id, counts = seed(client)
        assert counts == {"ready": 15, "unsupported": 1, "parse_error": 2}
        assert client.get(f"/vacancies/{vacancy_id}/analyses").json() == []
        assert client.get(f"/vacancies/{vacancy_id}").json()["title"] == TITLE
        criteria = client.get(f"/vacancies/{vacancy_id}/criteria").json()
        assert [(item["description"], item["priority"]) for item in criteria] == list(CRITERIA)
        resumes = client.get(f"/vacancies/{vacancy_id}/resumes").json()
        assert len(resumes) == 18

        # Same correct PDF bytes are a duplicate, not a nineteenth record.
        first_spec, first_bytes = corpus()[0]
        duplicate = client.post(
            f"/vacancies/{vacancy_id}/resumes",
            files={"files": (first_spec.filename, first_bytes, "application/pdf")},
        ).json()["results"][0]
        assert duplicate["duplicate"] is True and duplicate["status"] == "ready"
        assert len(client.get(f"/vacancies/{vacancy_id}/resumes").json()) == 18

        started = client.post(f"/vacancies/{vacancy_id}/analyses")
        assert started.status_code == 202
        run_id = started.json()["id"]
        run = finished(client, run_id)
        assert (run["status"], run["total"], run["completed"], run["failed"]) == (
            "completed_with_errors", 18, 15, 3,
        )
        assert run["provider"] == "fake"
        assert [item["description"] for item in run["criterion_snapshot"]] == [
            "Python", "SQL", "Docker",
        ]
        by_name = {
            item["filename"]: item
            for item in client.get(f"/analyses/{run_id}/results").json()["results"]
        }
        assert set(by_name) == {spec.filename for spec in SPECS}
        snapshot = {item["description"]: item["id"] for item in run["criterion_snapshot"]}
        for expected in manifest():
            item = by_name[expected["filename"]]
            if expected["parse_status"] != "ready":
                assert item["status"] == "failed" and item["findings"] == []
                assert item["error"] == "resume_not_ready"
                continue
            assert item["status"] == "completed"
            actual = {name: next(
                finding for finding in item["findings"] if finding["criterion_id"] == criterion_id
            ) for name, criterion_id in snapshot.items()}
            assert {name: finding["status"] for name, finding in actual.items()} == expected["findings"], expected["filename"]
            resume_id = item["resume_id"]
            detail = client.get(f"/resumes/{resume_id}").json()
            text = detail["extracted_text"]
            assert text
            for finding in actual.values():
                quote = finding["evidence_quote"]
                if finding["status"] == "not_found":
                    assert quote is None and finding["evidence_page"] is None
                    continue
                assert quote and quote in text
                if expected["filename"].endswith(".pdf"):
                    page_number = finding["evidence_page"]
                    assert isinstance(page_number, int) and page_number >= 1
                    page = detail["source_pages"][page_number - 1]
                    assert page["page"] == page_number
                    assert quote in page["text"]
                else:
                    assert finding["evidence_page"] is None

        two_pages = by_name["09-two-pages.pdf"]["findings"]
        assert {finding["criterion_id"]: finding["evidence_page"] for finding in two_pages} == {
            snapshot["Python"]: 1, snapshot["SQL"]: 2, snapshot["Docker"]: 2,
        }
        assert {finding["criterion_id"]: finding["evidence_quote"] for finding in two_pages} == {
            snapshot["Python"]: "Experience: Python",
            snapshot["SQL"]: "Familiar with SQL",
            snapshot["Docker"]: "Experience: Docker",
        }
        old_results = client.get(f"/analyses/{run_id}/results").json()
        assert client.patch(
            f"/criteria/{criteria[1]['id']}", json={"description": "Kubernetes"}
        ).status_code == 200
        new_start = client.post(f"/vacancies/{vacancy_id}/analyses")
        assert new_start.status_code == 202
        second_id = new_start.json()["id"]
        second = finished(client, second_id)
        assert (second["completed"], second["failed"]) == (15, 3)
        assert [item["description"] for item in second["criterion_snapshot"]] == [
            "Python", "Kubernetes", "Docker",
        ]
        for item in client.get(f"/analyses/{second_id}/results").json()["results"]:
            if item["status"] == "completed":
                new_id = second["criterion_snapshot"][1]["id"]
                assert next(f for f in item["findings"] if f["criterion_id"] == new_id)["status"] == "not_found"
        assert client.get(f"/analyses/{run_id}").json()["criterion_snapshot"] == run["criterion_snapshot"]
        assert client.get(f"/analyses/{run_id}/results").json() == old_results

    with TestClient(create_app(database_url=database_url, upload_dir=upload_dir)) as reopened:
        assert reopened.get(f"/analyses/{run_id}/results").json() == old_results
        assert reopened.get(f"/analyses/{second_id}").json()["status"] == "completed_with_errors"
        with pytest.raises(RuntimeError, match="already exists"):
            seed(reopened)
        assert len(reopened.get("/vacancies").json()) == 1


@pytest.mark.parametrize("url", ["https://127.0.0.1:8000", "http://example.com", "http://127.0.0.1:8000/docs", "http://user@localhost:8000"])
def test_seed_rejects_nonlocal_or_nonroot_url(url: str) -> None:
    with pytest.raises(ArgumentTypeError):
        local_base_url(url)

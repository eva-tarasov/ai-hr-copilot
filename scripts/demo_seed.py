"""Seed the local FastAPI demo via its public HTTP endpoints."""

import argparse
from collections import Counter
from urllib.parse import urlsplit

import httpx

from scripts.demo_fixtures import CRITERIA, SPECS, corpus

TITLE = "AI HR Copilot — Synthetic Demo"
DESCRIPTION = "Synthetic Python backend role for a local, offline demonstration."


def seed(client: httpx.Client) -> tuple[int, Counter[str]]:
    health = client.get("/health")
    health.raise_for_status()
    if health.json() != {"status": "ok"}:
        raise RuntimeError("Unexpected /health response")

    existing = client.get("/vacancies")
    existing.raise_for_status()
    matches = [item for item in existing.json() if item["title"] == TITLE]
    if matches:
        ids = ", ".join(str(item["id"]) for item in matches)
        raise RuntimeError(
            f"Demo vacancy already exists (ID: {ids}). Use it in Streamlit or start with a separate SQLite; no second vacancy was created."
        )

    documents = corpus()  # Fail before any writes if fixture generation fails.
    if len(documents) != len(SPECS):
        raise RuntimeError("Incomplete demo corpus")
    vacancy_response = client.post("/vacancies", json={"title": TITLE, "description": DESCRIPTION})
    vacancy_response.raise_for_status()
    vacancy_id = vacancy_response.json()["id"]
    for order, (name, priority) in enumerate(CRITERIA):
        response = client.post(
            f"/vacancies/{vacancy_id}/criteria",
            json={"description": name, "priority": priority, "display_order": order},
        )
        response.raise_for_status()

    response = client.post(
        f"/vacancies/{vacancy_id}/resumes",
        files=[("files", (spec.filename, data, "application/octet-stream")) for spec, data in documents],
    )
    response.raise_for_status()
    results = response.json()["results"]
    if len(results) != len(documents):
        raise RuntimeError("Server returned an incomplete upload batch")
    for (spec, _), result in zip(documents, results, strict=True):
        if result["filename"] != spec.filename or result["status"] != spec.parse_status:
            raise RuntimeError(f"Unexpected upload result for {spec.filename}: {result['status']}")
    counts = Counter(item["status"] for item in results)

    first_spec, first_data = documents[0]
    duplicate = client.post(
        f"/vacancies/{vacancy_id}/resumes",
        files={"files": (first_spec.filename, first_data, "application/pdf")},
    )
    duplicate.raise_for_status()
    duplicate_result = duplicate.json()["results"][0]
    if not duplicate_result["duplicate"] or duplicate_result["resume_id"] != results[0]["resume_id"]:
        raise RuntimeError("Duplicate check failed")
    listed = client.get(f"/vacancies/{vacancy_id}/resumes")
    listed.raise_for_status()
    if len(listed.json()) != len(documents):
        raise RuntimeError("Unexpected number of unique resume records")
    return vacancy_id, counts


def local_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        raise argparse.ArgumentTypeError("--base-url must be a local HTTP root URL")
    return value.rstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic HR demo data through local FastAPI")
    parser.add_argument("--base-url", type=local_base_url, default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        with httpx.Client(base_url=args.base_url, timeout=120) as client:
            vacancy_id, counts = seed(client)
    except (httpx.HTTPError, RuntimeError) as error:
        parser.exit(1, f"Demo seed failed: {error}\n")
    print(f"Vacancy ID: {vacancy_id}")
    print(f"Unique resumes: {sum(counts.values())}; ready={counts['ready']}, unsupported={counts['unsupported']}, parse_error={counts['parse_error']}")
    print("Duplicate upload: recognized; no additional resume record")
    print("Open http://127.0.0.1:8501, select the demo vacancy, then click «Запустить анализ».")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

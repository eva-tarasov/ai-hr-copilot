# S06a demo verification report

**Date:** 2026-10-31 (Europe/Moscow). **State:** implementation ready for PR review; S06a has no PR or reviewed SHA yet. Base `main` SHA: `b9ab5cdcb50de8866c06994bb42b5c6a25e96485` (S05 merge). The implementation commit is the `feat/s06a-demo` commit containing this report; it is not a reviewed release.

## Environment and corpus

- macOS local environment, Python 3.13.0, FastAPI 0.162.0, Streamlit 1.66.1, PyMuPDF 1.28.2, python-docx 1.2.0, SQLAlchemy 2.1.6; existing `.venv` used, no dependency changes.
- Temporary SQLite and upload storage under `/private/tmp/aihr-s06a.1VD5Dt/`; FastAPI at `127.0.0.1:8000`, Streamlit at `127.0.0.1:8501`, `LLM_PROVIDER=fake`. No external HTTP/API calls.
- `scripts.demo_fixtures` creates 18 unique synthetic documents in memory: 8 valid PDF, 7 valid DOCX, one textless PDF, one malformed PDF, one malformed DOCX. The same `SPECS` generate the bytes and the manifest (`python -m scripts.demo_fixtures` prints filename, parsing status, expected Python/SQL/Docker findings and special case). No generated binary is tracked.
- Demo vacancy criteria: Python required, SQL required, Docker preferred. Corpus covers direct experience, mere skills-list mentions, missing claims, contradictions, explicit negative claims, a two-page PDF, and instruction-like text ignored by FakeProvider.

## Commands and observed outcomes

| Command / action | Observed result |
|---|---|
| `.venv/bin/python -m pytest -q` | `204 passed, 6 warnings in 5.69s` in the final full run. The warnings originate from Starlette/httpx and PyMuPDF SWIG deprecations. An earlier full run caught a mistake in the new reproducibility assertion (`203 passed, 1 failed`); the assertion was fixed and the full suite reran successfully. |
| `.venv/bin/python -m compileall backend ui scripts tests` | Exit 0; all four trees listed, test modules compiled. |
| `.venv/bin/python -m pip check` | `No broken requirements found.` pip also reported that its cache directory was not writable, so it disabled the cache. |
| `git diff --check` | Exit 0, no output. |
| Local Uvicorn startup with separate `DATABASE_URL`, `UPLOAD_DIR`, `LLM_PROVIDER=fake` | Started successfully on `127.0.0.1:8000`. Initial sandboxed bind was denied; retry with local execution permission succeeded. |
| `.venv/bin/python -m scripts.demo_seed --base-url http://127.0.0.1:8000` | Vacancy ID 1; 18 unique resumes: 15 ready, 1 unsupported, 2 parse_error. Valid PDF repeat recognized; no nineteenth record. Initial sandboxed loopback request was denied; retry with local execution permission succeeded. |
| Repeating the seed against the same DB | Exited 1 with `Demo vacancy already exists (ID: 1)` and guidance to reuse it or choose a separate SQLite. No second vacancy created. |
| Live `POST /vacancies/1/analyses`, then `GET /analyses/1` and results | Run #1 reached `completed_with_errors`: total 18, completed 15, failed 3, interrupted 0. Snapshot is Python/SQL/Docker; results contain 15 complete findings sets and three `resume_not_ready` errors. |
| Live Streamlit browser | Backend available; vacancy and three priorities visible; active resume table rendered; second analysis started by UI; history showed run #2 and 15 completed/3 errors. Matrix showed Unicode labels and separate document status. `09-two-pages.pdf` details showed exact `Experience: Python` on page 1, `Familiar with SQL` and `Experience: Docker` on page 2. |

Run #1's server timestamps were `started_at=2026-10-31T16:53:19.798643` and `completed_at=2026-10-31T16:53:19.843212` UTC: about **44.6 ms** for this tiny local FakeProvider workload. This is not a performance or HR productivity benchmark. Upload duration was not separately measured. The five-minute employer presentation itself was not timed.

## Automated checks and evidence

`tests/test_demo.py` uses its own temporary SQLite and upload directory. It compares a second generation of all 18 binaries byte for byte, parses each generated file, checks 15 ready/1 unsupported/2 parse_error, and confirms PDF page maps with no invented DOCX page numbers. The seed is exercised through TestClient and guarded against a repeat vacancy. A FakeProvider run checks all 45 stored finding statuses against the manifest and all non-empty quotes as exact substrings of source text and the cited PDF page. For the two-page PDF, it asserts the **exact** three evidence quotes and page numbers 1, 2, 2. It verifies that malformed documents fail individually, duplicate import does not add a row, previous results survive reopening the app, and a changed SQL criterion (`Kubernetes`) yields a new snapshot while the old one and old results stay unchanged.

The browser check covered selected demo views and a run started through the UI. It did not repeat the criterion-change scenario manually in the browser; that behavior is covered by the temporary SQLite integration test. It did not check a real OpenAI request, macOS Dark Mode, or a timed presentation.

## Known limits and risks before presentation

- FakeProvider follows narrow deterministic phrase rules; no claim about real model accuracy or decision quality follows from this corpus. HR must inspect evidence and make decisions.
- Scanned/textless PDF remains unsupported without OCR. Corrupt PDF/DOCX appear as failed documents in the run; they do not block the other 15.
- Seed refuses any existing vacancy with the same title, including a partial seed left by a network/API error after vacancy creation. It never deletes data; use a separate temporary SQLite to retry cleanly.
- Binary reproducibility was checked with the installed library versions. A different PyMuPDF/python-docx version may produce different SHA-256 bytes even with the same synthetic text. Duplicate behavior is verified with identical bytes in one environment.
- Streamlit 1.66.1 logged a deprecation warning for the existing `use_container_width` argument. The UI worked in the browser; S06a does not change S05 UI compatibility code.
- Local in-process dispatcher and SQLite have the v0.1 restart and scale limitations recorded in `progress.md` and ADR-001. CSV export and persistent HR review notes remain outside S06a. No real documents, secrets, DB, or generated PDF/DOCX are part of the working tree.

# v0.1 release QA — S06b Part 2

## Scope and observed checks

Base: PR #8 merged at `4f198711149f47d2f1be20329abfaf411903c5e1`; current changes are uncommitted and await review. Run the commands from the repository root with Python 3.13 and the existing `.venv`:

```sh
python -m pytest -q
python -m compileall backend ui scripts tests
python -m pip check
git diff --check
```

Observed on 2026-11-02: `.venv/bin/python -m pytest -q` returned **215 passed, 6 warnings in 6.81s**; compileall and `git diff --check` exited 0; `pip check` reported `No broken requirements found` with a pip cache permission warning. The warnings include Starlette/httpx and PyMuPDF SWIG deprecations. Automated checks use temporary SQLite and synthetic data. They cover restart interruption (including shutdown during DB work), invalid/incomplete provider output, citation validation, per-document failures, active-run archive conflict, repeat analysis, frozen criteria, persistent HRReview, CSV Unicode/failed results, prohibited criteria before provider calls and untrusted instruction handling. No real OpenAI request was made.

Local HTTP smoke: FastAPI with FakeProvider on a fresh temporary SQLite accepted the demo seed (18 unique documents: 15 ready, one unsupported and two parse errors), completed run #1 with 15 completed and three failed, returned `Experience: Python` on PDF page 1, and saved/read a synthetic HR review. This was an API-level local flow; no new browser or Excel walkthrough was performed in Part 2. The server was stopped afterwards.

For a local full flow, follow `README.md` and `docs/DEMO_SCRIPT.md`: start FastAPI with `LLM_PROVIDER=fake` and a new temporary SQLite, start Streamlit, run the demo seed, select the vacancy, inspect criteria and 18 documents, start analysis, refresh progress, inspect evidence and an error, save a synthetic HR note, download CSV, and reopen a prior run after changing a criterion. Use separate local terminals and keep generated files outside Git. FakeProvider is a deterministic adapter; it is not an LLM quality benchmark.

## Immutable inputs and responsiveness

Each newly created run saves each selected document's parsing status, extracted text and source pages in a new `analysis_input_snapshots` table in the same transaction as the run. Existing SQLite databases gain the table through `create_all` without altering columns. Earlier completed runs remain readable but their original input snapshots cannot be reconstructed; interrupted older runs must be restarted as new runs. A missing snapshot fails closed. The snapshot retains a copy of potentially sensitive extracted text, increasing database storage and retention obligations. The existing resume detail API still displays the current resume text; if data is modified outside the app, compare it with that limitation in mind.

Controlled local TestClient measurement with a simulated 0.8-second repository operation: the original synchronous execution delayed `/health` to 0.830 s. Replaying the original synchronous scheduling against the same instrumented setup gave `/health` 0.824 s and `/analyses/1` 0.825 s. With thread offload, both returned in 0.003 s. These are single synthetic measurements, not a throughput benchmark. Each operation creates and closes its own SQLAlchemy session in its worker thread; shutdown waits for in-flight work before disposing the engine.

## Release limits and gates

- Local SQLite and in-process worker only; a restart interrupts unfinished work, and there is no durable queue or multiworker guarantee.
- Run creation still performs synchronous SQLite work in its async request handler; BL-001 measurements and the thread offload cover dispatcher operations, not all request-path database work.
- FakeProvider cannot establish real-model accuracy; citation validation is limited to source matching and heuristic relevance. Human review remains mandatory.
- OCR, authentication, hosted deployment, real applicant data and ranking are out of scope. CSV and the database may contain sensitive text; keep both private.
- Backlog remains open until reviewed and linked to a merge: BL-001 and BL-002 have local candidate fixes; BL-003 (real-provider backoff), BL-004 (multipart private API), BL-005 (test client deprecation) and BL-006 (citation paraphrases) remain open. See `BACKLOG.md` for details.
- Local demo readiness is subject to review and owner acceptance. Real LLM readiness is **not established**; `docs/OPENAI_SMOKE_PLAN.md` is a proposed separately authorized smoke-test, not permission to send requests.

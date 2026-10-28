# S04 — Local batch analysis without blocking UI


> **Codex operating instructions for this step:** Read `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `progress.md`. Check that this is the currently approved step. Present a short implementation plan and explicitly list which files you expect to edit. Do only the scope below. Implement tests including negative cases. Run `python -m pytest -q` and suitable launch checks (if impossible, say why). Update `progress.md` truthfully; do not invent PR/SHA or mark your own review PASS. Never run git push/merge/deploy or access external APIs without explicit approval. At the end, report changed files, test commands with actual results, manual verification, limitations, and STOP.


## Goal
Start analysis for a vacancy and track completed, pending and failed resumes. Locally process 10–20 synthetic files with bounded concurrency.

## Scope
- SQLAlchemy `AnalysisRun`, `ResumeAnalysis`, `CriterionFinding` persistence, with `criterion_snapshot_json`, provider/model/prompt version and run timestamps.
- `POST /vacancies/{id}/analyses`, `GET /analyses/{id}`, `GET /analyses/{id}/results`.
- Local in-process bounded background dispatcher with semaphore MAX_CONCURRENT_ANALYSES=2. Save results of each resume immediately. Do not run all LLM calls inside request response path.
- On app restart, existing incomplete runs must appear as INTERRUPTED or FAILED with actionable retry; no silent "completed". This is not a production durable queue.
- Retry only transient API errors with capped backoff; non-retryable parsing/validation errors isolate that resume.
- Tests with Fake adapter for statuses, 3 resumes, one error, snapshot immutability, restart simulation where feasible, idempotent run submission where needed. No network calls.

## Acceptance
- Start run; poll status and results from another endpoint.
- A single invalid resume fails without terminating others.
- Save per-resume evidence and do not make automated hiring decisions.

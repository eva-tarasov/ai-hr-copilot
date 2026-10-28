# S01 — Vacancies and criteria backend


> **Codex operating instructions for this step:** Read `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `progress.md`. Check that this is the currently approved step. Present a short implementation plan and explicitly list which files you expect to edit. Do only the scope below. Implement tests including negative cases. Run `python -m pytest -q` and suitable launch checks (if impossible, say why). Update `progress.md` truthfully; do not invent PR/SHA or mark your own review PASS. Never run git push/merge/deploy or access external APIs without explicit approval. At the end, report changed files, test commands with actual results, manual verification, limitations, and STOP.


## Goal
Persistent vacancy and criterion management via FastAPI; no resume handling yet.

## Scope
- SQLAlchemy 2.x models and DB session setup for SQLite; lightweight schema creation for local MVP, document that migrations in v0.2 will be explicit.
- Vacancy: id/title/description/timestamps; Criterion: id/vacancy id/description/priority required|preferred/active/order.
- Pydantic input/output schemas and validation (non-empty title/criterion, length bounds, invalid priority rejected).
- API: GET/POST `/vacancies`, GET/PATCH `/vacancies/{id}`, GET/POST `/vacancies/{id}/criteria`, PATCH/DELETE `/criteria/{id}`.
- Layer API → service → repository. No SQLAlchemy session or ORM in Streamlit. Clear 404/422 errors.
- Tests use a temporary SQLite database and cover CRUD, validation, vacancy/criteria isolation, not-found IDs.

## Acceptance
- Create vacancy + 2 criteria, retrieve them via FastAPI docs.
- Readable business code isolated from HTTP and persistence.
- `python -m pytest -q` passes; no OpenAI calls.
- No candidate scores, applicant ranking or future-phase features.

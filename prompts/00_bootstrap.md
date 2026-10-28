# S00 — Initialize repo and runnable skeleton


> **Codex operating instructions for this step:** Read `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `progress.md`. Check that this is the currently approved step. Present a short implementation plan and explicitly list which files you expect to edit. Do only the scope below. Implement tests including negative cases. Run `python -m pytest -q` and suitable launch checks (if impossible, say why). Update `progress.md` truthfully; do not invent PR/SHA or mark your own review PASS. Never run git push/merge/deploy or access external APIs without explicit approval. At the end, report changed files, test commands with actual results, manual verification, limitations, and STOP.


## Goal
Create the smallest runnable Python application skeleton for Mac. First project milestone, nothing from business functionality yet.

## Scope
- `pyproject.toml` with Python 3.13-compatible dependencies FastAPI, Uvicorn, Streamlit, SQLAlchemy, Pydantic, pytest, httpx and packages needed by the existing roadmap (no extra large frameworks). Use simple pip/venv workflow.
- `backend/app/main.py` with GET `/health` returning `{ "status": "ok" }`.
- `ui/app.py` showing `AI HR Copilot`, an API health check via HTTP (`http://127.0.0.1:8000`) with a friendly offline error; no direct DB calls from UI.
- package `__init__.py`, configuration via env with safe defaults (fake provider, local SQLite path), `.env.example`, safe `.gitignore`, README install/run instructions.
- Minimal `tests/test_health.py` using `TestClient`; do not require API key for tests.
- Retain docs and prompts as provided, and update `progress.md` to implementation-ready/review-needed with commands run.

## Acceptance
- Fresh venv: `python -m pip install -e '.[dev]'` succeeds.
- `python -m pytest -q` passes.
- `python -m uvicorn backend.app.main:app --reload` runs locally; `/health` responds.
- In second terminal, `python -m streamlit run ui/app.py` shows app and healthy API.
- No JS frontend, no Docker/DB schemas/business logic yet.

## Ask me to verify
Return exact terminal commands, actual outputs, and a list of files added. Stop; I will inspect and commit in GitHub.

# AI HR Copilot — progress

**Updated:** 2026-10-28
**Current phase:** S02 — Secure resume upload and PDF/DOCX parsing
**Current phase state:** IMPLEMENTED — AWAITING ARCHITECTURE REVIEW (not approved)
**Target:** local demo v0.1 Fri 2026-10-30; hardened v0.1 Mon 2026-11-02.
**Approved architecture:** ADR-001 in `docs/DECISIONS.md`.
**Latest reviewed PR / SHA:** PR: [https://github.com/eva-tarasov/ai-hr-copilot/pull/2](https://github.com/eva-tarasov/ai-hr-copilot/pull/2); Reviewed SHA: `d60b5da699e5b95e77c9b4a60c4a1ca1699eb6e6`.

## Phase checklist
- [x] S00 — Repo + toolchain + runnable FastAPI/Streamlit + tests
- [x] S01 — Vacancies and criteria CRUD
- [ ] S02 — Upload, PDF/DOCX extraction, duplicates and errors
- [ ] S03 — Fake and OpenAI LLM adapters, strict schema, evidence
- [ ] S04 — Bounded batch analysis and statuses
- [ ] S05 — UI vertical slice and results/CSV (scope adjustable)
- [ ] S06a — Friday demo, sample fixtures, smoke checks
- [ ] S06b — Monday hardening, docs and QA
- [ ] S07 — v0.2 server DB + durable worker [LOCKED]
- [ ] S08 — v0.2 DeepSeek/Kimi adapters and evals [LOCKED]
- [ ] S09 — v0.2 VPS/HTTPS/auth/security [LOCKED]

## Work log
| Date | Phase | Branch / PR / SHA | Test evidence | Review | Notes |
|---|---|---|---|---|---|
| 2026-10-28 | S00 | `feat/s00-bootstrap`; [PR #1](https://github.com/eva-tarasov/ai-hr-copilot/pull/1); `1a46f2be80e2e0866487b68041c33b5ce6fa826f` | `pytest`: 2 passed; `compileall backend ui`: successful; FastAPI `GET /health`: HTTP 200, `{"status":"ok"}`; Streamlit opens and shows `Backend is available`; after stopping FastAPI, shows `Backend is unavailable` | PASS | Architecture review passed; manual checks confirmed by project owner on 2026-10-28. |
| 2026-10-28 | S01 | `feat/s01-vacancy-criteria`; [PR #2](https://github.com/eva-tarasov/ai-hr-copilot/pull/2); `d60b5da699e5b95e77c9b4a60c4a1ca1699eb6e6` | `pytest -q`: 8 passed, 1 third-party deprecation warning; `compileall backend ui` passed (reconfirmed 2026-10-28); `git diff --check` passed; TestClient CRUD, 404/422, vacancy isolation, and persistence on temporary SQLite passed; live FastAPI `/health` and `/openapi.json`: HTTP 200 | PASS | Review PASS confirmed by project owner; S01 complete. |
| 2026-10-28 | S02 | `feat/s02-resume-upload`; PR/SHA — | `pip install -e '.[dev]'` succeeded; `pytest -q`: 23 passed, 6 third-party warnings; `compileall backend ui`, `git diff --check`, and `pip check` passed; TestClient covered PDF/DOCX, mixed batch, malformed/empty/unsupported/oversized files, dedupe, isolation, restart persistence, cleanup on simulated DB/storage failures, and multipart OpenAPI metadata; live Uvicorn `/health` and `/openapi.json`: HTTP 200 | WAITING | Implementation ready for separate architecture review; S02 checklist remains open until human PASS. |

## Gates
A phase is COMPLETE only after tests and human review PASS. Codex updates this file with truthful evidence and leaves PR/SHA blank until known. Do not mark PASS on own authority.

## Blockers
- OpenAI API key with billing needed for real-model smoke test; Fake model works without key.
- Only synthetic or authorized de-identified resumes permitted for demo.

## S00 risks / limits
- `fastapi.testclient` emits a Starlette deprecation warning for `httpx`; tests pass, but the dependency transition should be assessed in a later approved phase.
- S00 checked only process startup, HTTP health, and UI availability states; it included no database, document, or LLM behavior.

## S01 risks / limits
- Startup `create_all` creates missing tables but does not migrate existing columns; explicit migrations remain a later design decision.
- Vacancy deletion is outside the documented S01 API. Criterion display order is a sortable integer; equal values use ID as a tie-breaker, and updates do not renumber peers.

## S02 risks / limits
- OCR and legacy `.doc` are unsupported. Oversized or storage-rejected files are returned per file but are not persisted because a complete content hash is unavailable.
- The per-file ingress cap uses Starlette multipart parser internals; recheck this behavior when upgrading Starlette. The batch limit is 20 files.

## Decisions / deviations
- ADR-001 accepted; no new dependencies or architecture shifts without Change Gate.

## Next action
Review the S02 diff and test evidence. Owner may commit/push and open a PR for architecture review; record actual PR/SHA when known. Begin S03 only after human review PASS and explicit approval.

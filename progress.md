# AI HR Copilot — progress

**Updated:** 2026-10-28
**Current phase:** S00 — Repository bootstrap
**Current phase state:** COMPLETE — REVIEW PASS
**Target:** local demo v0.1 Fri 2026-10-30; hardened v0.1 Mon 2026-11-02.
**Approved architecture:** ADR-001 in `docs/DECISIONS.md`.
**Latest reviewed PR / SHA:** PR: [https://github.com/eva-tarasov/ai-hr-copilot/pull/1](https://github.com/eva-tarasov/ai-hr-copilot/pull/1); Reviewed SHA: `1a46f2be80e2e0866487b68041c33b5ce6fa826f`.

## Phase checklist
- [x] S00 — Repo + toolchain + runnable FastAPI/Streamlit + tests
- [ ] S01 — Vacancies and criteria CRUD
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

## Gates
A phase is COMPLETE only after tests and human review PASS. Codex updates this file with truthful evidence and leaves PR/SHA blank until known. Do not mark PASS on own authority.

## Blockers
- OpenAI API key with billing needed for real-model smoke test; Fake model works without key.
- Only synthetic or authorized de-identified resumes permitted for demo.

## S00 risks / limits
- `fastapi.testclient` emits a Starlette deprecation warning for `httpx`; tests pass, but the dependency transition should be assessed in a later approved phase.
- S00 checks only process startup, HTTP health, and UI availability states. No database, document, or LLM behavior exists yet.

## Decisions / deviations
- ADR-001 accepted; no new dependencies or architecture shifts without Change Gate.

## Next action
Complete merge of PR #1 and sync the local `main` branch. Begin S01 only after explicit confirmation from the project owner.

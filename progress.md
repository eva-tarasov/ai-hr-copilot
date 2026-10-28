# AI HR Copilot — progress

**Updated:** 2026-10-28
**Current phase:** S00 — Repository bootstrap
**Current phase state:** IMPLEMENTED — AWAITING ARCHITECTURE REVIEW (not approved)
**Target:** local demo v0.1 Fri 2026-10-30; hardened v0.1 Mon 2026-11-02.
**Approved architecture:** ADR-001 in `docs/DECISIONS.md`.
**Latest reviewed PR / SHA:** none.

## Phase checklist
- [ ] S00 — Repo + toolchain + runnable FastAPI/Streamlit + tests
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
| 2026-10-28 | S00 | `feat/s00-bootstrap`; PR/SHA — | Python 3.13.0; `pip install -e '.[dev]'` succeeded; `pytest -q`: 2 passed, 1 third-party deprecation warning; `compileall backend ui`, `pip check`, `git diff --check` passed; FastAPI `/health` returned `{"status":"ok"}`; Streamlit started and AppTest passed for healthy/offline states | WAITING | S00 implementation ready for separate architecture review; checklist remains open until human PASS. |

## Gates
A phase is COMPLETE only after tests and human review PASS. Codex updates this file with truthful evidence and leaves PR/SHA blank until known. Do not mark PASS on own authority.

## Blockers
- GitHub repository needs to be created/linked by owner.
- OpenAI API key with billing needed for real-model smoke test; Fake model works without key.
- Only synthetic or authorized de-identified resumes permitted for demo.

## S00 risks / limits
- `fastapi.testclient` emits a Starlette deprecation warning for `httpx`; tests pass, but the dependency transition should be assessed in a later approved phase.
- S00 checks only process startup, HTTP health, and UI availability states. No database, document, or LLM behavior exists yet.

## Decisions / deviations
- ADR-001 accepted; no new dependencies or architecture shifts without Change Gate.

## Next action
Review the S00 diff and test evidence. Owner may commit/push and open a PR for architecture review; record actual PR/SHA when known. Begin S01 only after human review PASS and explicit approval.

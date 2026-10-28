# AI HR Copilot — progress

**Updated:** 2026-10-28
**Current phase:** S00 — Repository bootstrap
**Current phase state:** NOT STARTED
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
| 2026-10-28 | S00 | — | — | WAITING | Kit prepared. Start first Codex prompt. |

## Gates
A phase is COMPLETE only after tests and human review PASS. Codex updates this file with truthful evidence and leaves PR/SHA blank until known. Do not mark PASS on own authority.

## Blockers
- GitHub repository needs to be created/linked by owner.
- OpenAI API key with billing needed for real-model smoke test; Fake model works without key.
- Only synthetic or authorized de-identified resumes permitted for demo.

## Decisions / deviations
- ADR-001 accepted; no new dependencies or architecture shifts without Change Gate.

## Next action
Run `prompts/00_bootstrap.md` in Codex, verify startup and tests, create feature branch/PR manually, send PR link + Codex report for review.

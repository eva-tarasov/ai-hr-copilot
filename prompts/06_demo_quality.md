# S06 — Friday demo / Monday hardening


> **Codex operating instructions for this step:** Read `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `progress.md`. Check that this is the currently approved step. Present a short implementation plan and explicitly list which files you expect to edit. Do only the scope below. Implement tests including negative cases. Run `python -m pytest -q` and suitable launch checks (if impossible, say why). Update `progress.md` truthfully; do not invent PR/SHA or mark your own review PASS. Never run git push/merge/deploy or access external APIs without explicit approval. At the end, report changed files, test commands with actual results, manual verification, limitations, and STOP.


## Goal
Deliver a predictable 5-minute employer demo; no new product features until core passes.

## Scope
- Generate (not commit real HR data) 15–20 varied, synthetic PDF/DOCX fixtures; store fixture generators in `tests/fixtures` so no personal info. Include tricky examples: technology name in skills only, clear project evidence, conflicting dates, no relevant experience, malicious "ignore previous instructions" text.
- `scripts/demo_seed.py` loads fixtures via API or commands and sets example vacancy + criteria; tests should be deterministic with FakeProvider.
- Run `python -m pytest -q`, static syntax checks, manual full flow, fault cases and rerun after modifying criteria. Record observed execution time, not invented productivity gains.
- Add CSV export/review note or reanalysis support only when core stable; document postponed work.
- For Monday: deployment via Docker Compose optional only once local happy path works (no public host, no real PII).
- README: full clean install, two start commands, demo script, env setup, common errors, screenshots only if actually captured.

## Acceptance
- Friday: no critical bugs in demo flow, 10–20 synthetic docs, persistent findings + evidence.
- Monday: good error states, repeatability, tests, docs, no secrets, honest limitation of v0.1 worker and model output.
- Provide demo script (5 mins) and final evidence report in `docs/DEMO_REPORT.md`.

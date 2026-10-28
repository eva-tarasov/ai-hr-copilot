# Roadmap — dates, scope, handoffs

**Wed Oct 28 2026**
- S00: bootstrap repository/tooling.
- S01: vacancies + criteria CRUD / API.
- S02: PDF/DOCX ingestion, validation + duplicate detection.

**Thu Oct 29 2026**
- S03: LLM analysis contract, OpenAI and Fake providers, evidence checks.
- S04: batch run states and progress (bounded local worker).
- S05: Streamlit UI end-to-end.

**Fri Oct 30 2026 — DEMO target**
- S06a: scripted 10–20 synthetic resume demo; fix P0 bugs and validate launch.
- If blocked: remove enhancements (CSV, notes, reanalysis) before compromising successful end-to-end story.

**Sat–Mon Oct 31–Nov 2 — hardened v0.1 target**
- S06b: tests, evidence validation, invalid files, error handling, CSV/review/reanalysis, Docker optionally if core is stable; stability and docs.

**v0.2 AFTER acceptance (no artificial deadline yet)**
- S07: PostgreSQL, durable worker/batch processing, real 1000 synthetic benchmark.
- S08: OpenAI/DeepSeek/Kimi provider adapters, model configuration, compare on labeled eval dataset.
- S09: VPS cloud deploy, HTTPS, auth, secret management, backups, privacy review.

## Sequence gate
Each Sxx: Codex in scoped branch → local verification → user commits/pushes → PR → ChatGPT architecture/review PASS/CHANGES → merge → update progress → proceed. One PR per step if feasible.

## Success metric
For first demo: process 10–20 synthetic resumes, show correct evidence per criterion, clear status and human review, no automated hiring decisions. No unsupported productivity promises; measure quality on labeled fixtures in v0.2.

# PRD — AI HR Copilot

## Problem
One job posting can receive around 1000 applications. HR spends hours manually opening resumes and checking professional experience against a job description. We want to reduce manual document reading and make findings auditable.

## Core principle
**Decision support, not automatic selection**. AI extracts evidence about job-related, user-approved criteria. HR reviews the evidence and remains responsible for all hiring decisions. A missing claim in a resume is not proof of missing skill. No automatic rejection, applicant scores, "fit percentages" or hidden ranking.

## User flow v0.1
1. Open list of vacancies; create project vacancy (title, description).
2. Add criteria, each `required` or `preferred` and editable; optional AI-suggested criteria is deferred.
3. Upload many `.pdf` and `.docx` resumes. Display file parsing statuses, duplicate detection by checksum, file and parse errors. Legacy `.doc` deferred.
4. Start analysis; see job progress and per-resume outcomes.
5. For each criterion see `confirmed`, `mentioned`, `not_found`, `conflicting`, evidence snippet/page where possible, and optional follow-up question.
6. Filter by **factual criterion statuses**, manually review/annotate, export CSV. No automated hiring decisions.

## v0.1 functional requirements
- Vacancy CRUD (at least create, list, detail, edit).
- Criteria CRUD with `required` or `preferred` priority; snapshot criteria when analysis begins.
- Multi-file upload, PDF text layer and DOCX parsing; size/type validation, checksum. OCR is deferred.
- OpenAI structured JSON to Pydantic; source quote verification against parsed text; no unsupported assertions or guessed evidence.
- Batch analysis at least 10–20 synthetic resumes demo, bounded concurrency; progress and per-document errors; retries only for transient failures.
- View stored results and source evidence. Export CSV and basic HR review flag/note.
- Deterministic FakeProvider used in tests; real OpenAI only with user-supplied key and explicit smoke test.

## Non-functional requirements
- Local macOS developer workflow, Python 3.13 where available; readable setup; one-command tests.
- API boundary independent of UI; no SDK calls in Streamlit UI.
- Async request limits; idempotent handling of duplicate file imports; no crash on one bad resume.
- Store an audit trail: model name, provider, prompt/schema version, analysis time/status; redact logs.
- 20 synthetic documents demo is acceptance; 1000 is design target / subsequent performance validation, NOT an MVP performance claim.

## Out of scope v0.1
- hh.ru integration; production authentication; multiuser roles; deploy; self-hosted LLM; OCR; RAG/vector DB; autonomous agents; automated hiring/rejection; candidate rankings; SSO; production-grade job queue; real applicant data.

## v0.2 after v0.1 acceptance
- Containerized hosted app with HTTPS, auth, safe storage and backups.
- PostgreSQL and dedicated worker/queue for recoverable 1000-document processing.
- Pluggable OpenAI, DeepSeek, Kimi (availability/capabilities verified for chosen accounts); settings + per-provider schema validation, timeouts, usage/cost tracking.
- A 50–100-item human-labeled eval fixture, model comparison and prompt regression tests; privacy and hiring compliance review prior to real data.

## v0.1 demo acceptance checklist
- [ ] Open list/create a vacancy, add/edit criteria.
- [ ] Import 10–20 synthetic PDF/DOCX (one invalid and one duplicate).
- [ ] See analysis start/progress, failures isolated.
- [ ] Open a resume, inspect per-criterion statuses + source evidence.
- [ ] Show human review/notes and CSV export.
- [ ] Re-run on revised criteria without re-uploading original files.
- [ ] Run tests; launch via documented commands.
- [ ] No secrets/real PII in repository; no auto decisions or candidate scores.

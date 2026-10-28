# Architecture v0.1 — AI HR Copilot

## Logical diagram

```
Streamlit Web UI
     | HTTP localhost
     v
FastAPI routers / Pydantic boundary
     |
     v
Application services (Vacancies, Documents, Analysis, Exports)
     |            |                |
     v            v                v
SQLAlchemy     Parsers        LLMProvider(Protocol)
Repository     PDF/DOCX         /              \
     |                       FakeProvider   OpenAIProvider
SQLite
```

## Directory concept
```
backend/app/api/
backend/app/schemas/
backend/app/models/
backend/app/repositories/
backend/app/services/
backend/app/parsing/
backend/app/llm/
backend/app/jobs/
backend/app/core/
backend/app/main.py
ui/app.py
tests/
```

## Core records
- `Vacancy(id, title, description, created_at, updated_at)`
- `Criterion(id, vacancy_id, text, priority, active, updated_at)`
- `Resume(id, vacancy_id, filename, sha256, extracted_text, status, parse_error, created_at)`
- `AnalysisRun(id, vacancy_id, criterion_snapshot_json, provider, model, schema_version, status, started_at, completed_at)`
- `ResumeAnalysis(id, run_id, resume_id, status, error, completed_at)`
- `CriterionFinding(id, resume_analysis_id, criterion_snapshot_id, status, evidence_quote, evidence_page, follow_up_question)`
- `HRReview(id, resume_id, vacancy_id, reviewed, note, updated_at)`

Names and schema can be refined during step 01 but preserve semantics and a frozen criterion snapshot per run. No score/auto decision.

## APIs (initial target, adjust with ADR if necessary)
- `GET/POST /vacancies`, `GET/PATCH /vacancies/{id}`
- `GET/POST /vacancies/{id}/criteria`, `PATCH/DELETE /criteria/{id}`
- `POST /vacancies/{id}/resumes` (multipart), `GET /vacancies/{id}/resumes`, `GET /resumes/{id}`
- `POST /vacancies/{id}/analyses`, `GET /analyses/{run_id}`, `GET /analyses/{run_id}/results`
- `PATCH /resumes/{id}/review`, `GET /vacancies/{id}/export.csv`

## LLM isolation
`ResumeAnalysisService` depends on an abstract `LLMProvider` exposing `analyze(resume_text, criteria_snapshot) -> LLMAnalysis`. Each concrete provider validates against Pydantic. For evidence, verify the quoted substring is present in extracted text (normalize whitespace) and downgrade to `not_found`/mark for review on mismatch; never silently invent evidence. Injection in resumes must be treated as untrusted data and cannot override system rules. Provider credentials from env only.

## v0.1 batch execution
For demo scale, allow only a single local running API instance and a bounded in-process async task dispatcher (e.g. semaphore 2). Save run/document statuses to SQLite and persist each result. If server restarts, mark interrupted jobs visibly and allow manual retry; do **not** claim durable exactly-once processing. Never process whole batch in one HTTP request. For v0.2 replace with dedicated worker and durable queue/storage.

## Safety + access
Local-only `127.0.0.1` by default; localhost HTTP, no real PII without authorization. Restrict uploads by content type, magic signature/safe parser checks and max file size, sanitize filenames, disable external links in uploads. `.env`, SQLite, uploaded files and exports ignored by Git. Logs redact resume content and keys.

## v0.2 evolution
Keep API + service layer; switch persistence to PostgreSQL, job dispatcher to separate worker/queue, replace local storage with restricted durable file storage. Add auth/RBAC/HTTPS, LLM provider registry, model-specific capabilities and eval-based selection. Roll out only after privacy/compliance assessment.

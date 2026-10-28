# S07 — v0.2 hosted database and durable worker (LOCKED)


> **Codex operating instructions for this step:** Read `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `progress.md`. Check that this is the currently approved step. Present a short implementation plan and explicitly list which files you expect to edit. Do only the scope below. Implement tests including negative cases. Run `python -m pytest -q` and suitable launch checks (if impossible, say why). Update `progress.md` truthfully; do not invent PR/SHA or mark your own review PASS. Never run git push/merge/deploy or access external APIs without explicit approval. At the end, report changed files, test commands with actual results, manual verification, limitations, and STOP.


DO NOT START until S06b is reviewed PASS and user authorizes v0.2.

## Goal
Move to PostgreSQL, separate worker and recoverable batch processing of 1000 synthetic resumes.

## Scope
- Alembic migrations, PostgreSQL Docker Compose for dev, transactional repositories.
- Separate worker process (choose Redis-backed queue or DB-backed job outbox via ADR, smallest reliable approach); deterministic retries, explicit idempotency/cancellation and job ownership.
- Object/file storage with access controls, retention/delete rules, backups.
- Load test with 1000 synthetic documents, collect throughput, failure rate, resource costs; no unverified performance claims.
- Maintain existing HTTP/UI contracts and tests.

## Acceptance
- Kill worker mid-run, restart worker, resume without missing/doubled applicant results.
- DB migrations roll forward on clean host; load test produces actual metrics.

# Architecture Decisions

## ADR-001 — Ship local end-to-end vertical slice first
**Status:** Accepted on 2026-10-28

**Decision:** Python FastAPI backend, Streamlit UI, SQLAlchemy + SQLite, PyMuPDF + python-docx, Pydantic, OpenAIAdapter + FakeAdapter behind Provider Protocol. Local-only first. Build minimal functioning flow before future-scale infrastructure.

**Why:** Deadline Friday 2026-10-30 for a demonstrable happy path, Monday 2026-11-02 for hardening. Most useful signal is a working product, test evidence and transparent architecture.

**Deferred:** PostgreSQL, Celery/Redis, RAG, LangGraph, LangChain, OCR, hh.ru integrations, model switcher UI, production auth/cloud, self-hosted LLM.

**Tradeoff:** In-process worker is not fault-tolerant on process crash, 1000 resumes unproven. These limits must be clearly disclosed. v0.2 can migrate behind abstractions.

## Change Gate
Any proposed deviation uses one decision:
- KEEP CURRENT: insufficient evidence to change.
- DEFER: useful but not essential for current release.
- RUN SMALL SPIKE: bounded experiment, explicit success/fail criteria.
- ADOPT: measurable benefit outweighs cost/risk and user approves.

Record future ADRs with context, options, decision, evidence and rollback impact.

## S05 implementation note — reversible local resume archive

**Scope:** Product UX improvements in PR #6; ADR-001 remains unchanged.

**Decision:** Keep `resumes` columns unchanged and add a small `resume_archives` table keyed by `resume_id`, with `archived_at`. Existing SQLite files gain this table through `create_all`; no destructive migration or data copy is needed. The default vacancy list and new run creation exclude archived resumes. History queries still read the original Resume and saved findings. Reupload by SHA returns the existing record and its archive state; only explicit restore makes it active again. Permanent DELETE retains its existing FK/history guard.

**Consistency:** Archive and run creation acquire a SQLite `BEGIN IMMEDIATE` write lock before checking active runs or selecting resumes. This serializes the two local transactions and rejects archiving during a pending/running run. The design is for the single local SQLite instance in ADR-001; it is not a multiworker/production locking design.

**Tradeoff and rollback:** Archive keeps the stored document and PII until separately deleted. Restoring an archive entry is reversible; permanent deletion of an unlinked document is not. Removing the feature later would require an explicit decision about what to do with archived rows; dropping the new table would make those resumes active again. No change is made to past criterion snapshots or evidence.

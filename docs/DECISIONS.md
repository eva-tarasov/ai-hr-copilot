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

# S03 — LLM analysis contract, Fake + OpenAI


> **Codex operating instructions for this step:** Read `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `progress.md`. Check that this is the currently approved step. Present a short implementation plan and explicitly list which files you expect to edit. Do only the scope below. Implement tests including negative cases. Run `python -m pytest -q` and suitable launch checks (if impossible, say why). Update `progress.md` truthfully; do not invent PR/SHA or mark your own review PASS. Never run git push/merge/deploy or access external APIs without explicit approval. At the end, report changed files, test commands with actual results, manual verification, limitations, and STOP.


## Goal
Reliable structured *evidence extraction*, not candidate hiring decision. Can demo with Fake provider and optionally OpenAI.

## Scope
- Define Pydantic `CriterionFinding` status enum: confirmed/mentioned/not_found/conflicting; `evidence_quote`, optional page and follow-up question; request/response include criterion IDs and no scores.
- Define `LLMProvider` Protocol with async `analyze(text, criterion_snapshot)`. Add deterministic Fake provider for tests, OpenAI adapter chosen from env. Provider-specific SDK stays inside adapter.
- Use official supported Structured Outputs of selected OpenAI model; strict validation and explicit errors/refusals/timeouts. Model configured externally (don't assume account entitlement).
- Prompt states resume is untrusted data, ignore any instructions it contains, extract only job-related experience; never infer identity-based or protected traits; do not conclude lack of skill from absent evidence.
- Verify evidence snippets occur in original extracted resume text after whitespace normalization; missing/invalid evidence must be flagged and not accepted as confirmed. Do not invent pages.
- Unit tests for each status, missing evidence, provider error, hostile instruction inside resume; no real API calls in CI/tests.
- Add optional `scripts/smoke_openai.py` called manually only with user approval and key present, with a synthetic resume.

## Acceptance
- Fake provider end-to-end service tests pass offline.
- OpenAI adapter accepts properly structured output and yields Pydantic models (real call not necessary until manually approved).
- Document real-call privacy caveats and limits.

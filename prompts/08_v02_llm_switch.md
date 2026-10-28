# S08 — Provider registry, DeepSeek/Kimi and evals (LOCKED)


> **Codex operating instructions for this step:** Read `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `progress.md`. Check that this is the currently approved step. Present a short implementation plan and explicitly list which files you expect to edit. Do only the scope below. Implement tests including negative cases. Run `python -m pytest -q` and suitable launch checks (if impossible, say why). Update `progress.md` truthfully; do not invent PR/SHA or mark your own review PASS. Never run git push/merge/deploy or access external APIs without explicit approval. At the end, report changed files, test commands with actual results, manual verification, limitations, and STOP.


DO NOT START until S07 is reviewed PASS and user authorizes.

## Goal
Switch LLM providers without rewriting business logic and quantify quality differences.

## Scope
- `LLMProvider` registry with provider capabilities; OpenAI, DeepSeek, Kimi adapters using official supported endpoints/config for currently selected models. Do not assume OpenAI compatibility implies JSON schema parity.
- Standard Pydantic normalization and validation, fallback/retry policy; no automatic cross-provider failover with personal data unless explicit authorized policy.
- Admin-only config via env initially; record provider, model, schema/prompt version, token/latency/cost (when returned).
- Evaluation suite with 50–100 labeled synthetic cases, precision/recall per criterion status, hallucinated citation count, failures, cost, latency; display honest measured trade-offs.
- Provider-specific contract tests with mocked network; optional consented real smoke tests.

## Acceptance
- Same resume+criteria fixture can be analyzed by two providers, storage/endpoint/UI unchanged.
- Comparative report with actual measurements and a rollback switch.

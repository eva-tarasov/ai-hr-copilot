# AI HR Copilot — development starter kit

This ZIP is **not an implemented application**. It contains the agreed architecture, product scope, Codex task prompts, review workflow and progress tracking to initialize the new repository.

## Setup
1. Create a private GitHub repository `ai-hr-copilot`, and a new ChatGPT Project named `AI HR Copilot`.
2. Copy `PROJECT_INSTRUCTIONS_CHATGPT.md` into ChatGPT Project Instructions (file itself may remain local or under `docs/`, not essential to the app).
3. Copy all files except this note, if desired, into the new local repo; keep root `AGENTS.md`, `progress.md`, `docs/`, `prompts/`.
4. Open the repo with Codex. Codex automatically reads `AGENTS.md` according to its project-instruction discovery.
5. Paste content of `prompts/00_bootstrap.md`. Approve only the scoped phase.
6. Verify tests, inspect diff, commit/push to a short-lived branch, open a PR. Share PR link for architectural review.
7. Continue only after PASS; update `progress.md` with actual PR/SHA and evidence.

## Practical workflow
- Codex writes code and tests. Human approves commits/push/merge/deploy.
- ChatGPT checks diffs and architecture and suggests targeted fixes.
- `progress.md` is the project status source of truth.
- No production candidate data in repo or LLM calls without explicit legal approval.
- Tests must use deterministic FakeProvider; OpenAI key may be unset until S03.

## v0.1 design
Streamlit frontend -> FastAPI -> application services -> SQLite/SQLAlchemy, parsing adapters, `LLMProvider` (Fake/OpenAI). v0.2 adds hosted DB, worker, provider plugins, access control.

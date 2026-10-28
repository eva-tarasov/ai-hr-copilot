# Message for ChatGPT after each Codex milestone

Use this template after pushing a scoped branch and opening a PR.

```
AI HR Copilot — review request
Phase: S__
GitHub repository: https://github.com/OWNER/ai-hr-copilot
PR: https://github.com/OWNER/ai-hr-copilot/pull/NUMBER
Base branch / head branch:
Commit SHA:
Codex summary:
Changed files:
Tests actually run + outputs:
Manual demo completed:
Known limitations / errors:
Question for architecture review:
```

## What reviewer checks
1. Fits approved phase; no premature dependencies/feature creep.
2. Layer boundaries and contracts, DB migrations/schema, LLM provider isolation.
3. Test coverage including negative/error cases and observed results.
4. Candidate data handling, PII, prompt injection, evidence grounding, no automatic ranking/rejection.
5. `progress.md` accuracy and alignment with ADR-001.

## Review resolution
- PASS: merge can be performed by owner; proceed with next step on command.
- CHANGES: scoped fixes required, same PR.
- BLOCKED: architecture/security/functional blocker; do not merge.

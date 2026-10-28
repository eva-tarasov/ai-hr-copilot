# S09 — VPS deployment, security, compliance (LOCKED)


> **Codex operating instructions for this step:** Read `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `progress.md`. Check that this is the currently approved step. Present a short implementation plan and explicitly list which files you expect to edit. Do only the scope below. Implement tests including negative cases. Run `python -m pytest -q` and suitable launch checks (if impossible, say why). Update `progress.md` truthfully; do not invent PR/SHA or mark your own review PASS. Never run git push/merge/deploy or access external APIs without explicit approval. At the end, report changed files, test commands with actual results, manual verification, limitations, and STOP.


DO NOT START until S08 is reviewed PASS and user authorizes hosting and budget.

## Goal
Private secure deployment to Kazakhstan VPS (or approved alternative) with access for HR.

## Scope
- Ubuntu + Docker Compose, reverse proxy HTTPS, domains, environment secret config, firewall, DB/volume backups, health and telemetry.
- Auth + RBAC (admin/HR), controlled deletion/retention, export audit, no public document URLs. Encrypt in transit; restrict outbound LLM providers.
- Review personal-data legal basis, DPA, provider country transfers and applicable automated-employment AI regulations before real applicant processing. Pilot synthetic only until approval.
- Test restore from backup and production smoke tests with de-identified fixtures.

## Acceptance
- Authenticated HTTPS access, access-control tests, secret handling, restore drill, documented deployment and rollback.
- No claims of compliance without an actual responsible review.

# S02 — Secure multiple resume upload and parsing


> **Codex operating instructions for this step:** Read `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `progress.md`. Check that this is the currently approved step. Present a short implementation plan and explicitly list which files you expect to edit. Do only the scope below. Implement tests including negative cases. Run `python -m pytest -q` and suitable launch checks (if impossible, say why). Update `progress.md` truthfully; do not invent PR/SHA or mark your own review PASS. Never run git push/merge/deploy or access external APIs without explicit approval. At the end, report changed files, test commands with actual results, manual verification, limitations, and STOP.


## Goal
Store many synthetic PDF/DOCX resumes against a vacancy and expose usable text for later analysis.

## Scope
- Multipart upload endpoint `POST /vacancies/{id}/resumes` accepting multiple files; list/get endpoints.
- Use PyMuPDF (text-only PDF) and python-docx. `.doc` and scanned PDF OCR **not supported** — return clear status, never fake extraction.
- Validate max size 10MB per file from config, supported extension and real content, handle malformed files gracefully, sanitize original filename; raw uploads stored under ignored `data/` or `uploads/` with generated IDs (not arbitrary paths).
- SHA-256 dedupe within vacancy; ensure identical content doesn't create multiple records in same vacancy.
- Persist extraction status: ready / unsupported / parse_error; extracted text; page metadata or suitable provenance; avoid resume text in logs.
- Tests include good PDF/DOCX generated synthetically at test runtime, corrupted file, oversized, duplicate, no file, nonexistent vacancy. Avoid external network.

## Acceptance
- 5 synthetic files upload; success/error statuses visible via API.
- Uploaded content and DB files ignored by Git.
- Failed individual file doesn't prevent others from reporting status.
- `python -m pytest -q` passes.

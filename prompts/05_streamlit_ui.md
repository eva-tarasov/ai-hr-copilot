# S05 — Web UI complete demo path


> **Codex operating instructions for this step:** Read `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `progress.md`. Check that this is the currently approved step. Present a short implementation plan and explicitly list which files you expect to edit. Do only the scope below. Implement tests including negative cases. Run `python -m pytest -q` and suitable launch checks (if impossible, say why). Update `progress.md` truthfully; do not invent PR/SHA or mark your own review PASS. Never run git push/merge/deploy or access external APIs without explicit approval. At the end, report changed files, test commands with actual results, manual verification, limitations, and STOP.


## Goal
From browser user can create a vacancy, define criteria, upload synthetic resumes, start analysis and inspect findings.

## Scope
- Streamlit UI calls FastAPI HTTP only, no direct ORM/LLM access.
- Pages/tabs: Vacancies list + create/edit; Vacancy Criteria required/preferred; Upload PDF/DOCX multiple; Analysis run/progress; Results table with factual filters; Resume details with finding evidence and linked original text where possible.
- Clear empty states, loading/error states and friendly Russian UI. Avoid unsubstantiated candidate fit % or scoring/ranking; do not hide not_found candidates.
- Optional if time: CSV export and HR-reviewed marker; do not compromise core flow to do them.
- Add API client wrappers in UI so routes not duplicated.
- Basic tests for client parsing and smoke scenario; screenshots in docs if convenient, no private PII.

## Acceptance
- Can reproduce 5-minute demo with 10–20 synthetics using Fake, and optionally approved OpenAI key.
- No crashes from one bad file, obvious progress state.
- UI not hard-coded to demo candidates.

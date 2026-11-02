# OpenAI smoke-test plan — approval required

No real request was made as part of S06b. Run this plan only after explicit owner approval, with synthetic data and an account-supported Structured Outputs model. Model availability, pricing, account access and billing have not been verified. Never use real resumes or HR notes.

## Setup and cost boundary

Use a fresh terminal, isolated SQLite and upload directory. Set the key interactively in the environment; do not put it in a command argument, repository file, shell history, screenshot or log. Replace the model placeholder with a model the owner has explicitly selected and verified for the account:

```sh
source .venv/bin/activate
SMOKE_DIR="$(mktemp -d /tmp/aihr-openai-smoke.XXXXXX)"
export DATABASE_URL="sqlite:///$SMOKE_DIR/smoke.sqlite3"
export UPLOAD_DIR="$SMOKE_DIR/uploads"
export LLM_PROVIDER=openai
export OPENAI_MODEL='OWNER_SELECTED_STRUCTURED_OUTPUT_MODEL'
read -rs OPENAI_API_KEY
export OPENAI_API_KEY
export MAX_CONCURRENT_ANALYSES=1
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The key is read from `OPENAI_API_KEY`; the model has no application default. The provider sends resume text and criteria to OpenAI with `store=False`, a 30-second SDK timeout and SDK retries disabled. The batch dispatcher retries timeout/transient failures at most twice (three attempts per document), with 0.05/0.1-second backoff. It does not honor `Retry-After`, set a request token cap or enforce a monetary budget. **One document does not guarantee one billable attempt or a fixed maximum cost**. Set an account budget/limit independently, inspect account costs, and stop rather than repeatedly retrying.

The adapter does not intentionally log keys or resume text and maps provider exceptions to safe codes. Keep OpenAI/HTTP client debug logging disabled; third-party debug logging and external infrastructure have not been audited for sensitive-data exposure. Never record raw request/response logs.

## Controlled procedure

1. Create an empty vacancy and one active professional criterion `Python` using `http://127.0.0.1:8000/docs`. Generate only `01-project-python.pdf` using the existing synthetic fixture generator into `$SMOKE_DIR`; upload that single file. Do not use `scripts.demo_seed`, which uploads 18 files.
2. Confirm the vacancy contains exactly one ready synthetic document and one active criterion. A second optional document, `02-skills-only.docx`, requires a separate explicit owner decision and changes the cost boundary. Never upload real resumes or HR notes.
3. Submit exactly one analysis via the local API and inspect its run ID, counters, provider/model, schema version and results. Check one finding per snapshot criterion, typed status, exact quote present in extracted source, correct PDF page and no unsupported claims. A model need not match the FakeProvider's labels; document discrepancies for human review.
4. Stop immediately on a refusal, incomplete/invalid response, authentication error, rate limit, unexpected retry, non-synthetic input, exposed secret, unexpected cost, or result requiring a change in scope. Shut down the local API; in-flight network cancellation is not a guarantee that an already submitted request is unbilled.
5. Record the owner-approved model, software SHA, synthetic fixture name/hash, criterion snapshot, timestamps, request count if observable, terminal status, sanitized error code, verified quote/page, and actual account usage/cost if available. Do not copy keys, authorization headers, raw provider logs, or personal data into Git or review comments.

Example fixture creation in the same shell where `SMOKE_DIR` was set (before starting the server, or in a separate terminal with the same path explicitly exported):

```sh
export SMOKE_DIR
python - <<'PY'
import os
from pathlib import Path
from scripts.demo_fixtures import SPECS, document_bytes
spec = next(item for item in SPECS if item.filename == '01-project-python.pdf')
print(Path(os.environ['SMOKE_DIR'], spec.filename).write_bytes(document_bytes(spec)))
PY
```

After the approved test, stop the API and clear `OPENAI_API_KEY` and `LLM_PROVIDER` from the shell. The temporary database, snapshots and documents remain private and require deliberate cleanup by the owner.

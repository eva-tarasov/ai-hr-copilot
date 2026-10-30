# AI HR Copilot

Local development app for the AI HR Copilot. The Russian Streamlit UI covers the local vacancy → criteria → resume upload → analysis → evidence flow through the FastAPI HTTP API.

## Requirements

- Python 3.13
- macOS or another system with Python `venv` and `pip`

## Install

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

The defaults work without a `.env` file or API key. To customize settings, copy `.env.example` to `.env`, edit it, then load it in each terminal before starting a process:

```sh
cp .env.example .env
set -a
source .env
set +a
```

`APP_ENV` controls FastAPI debug mode (`development` enables it); `BACKEND_URL` is the FastAPI base URL used by Streamlit. `DATABASE_URL` defaults to `sqlite:///./data/hr_copilot.sqlite3`; `UPLOAD_DIR` defaults to `uploads`; `MAX_UPLOAD_MB` defaults to 10 per file. Streamlit's local `.streamlit/config.toml` also limits its file picker to 10 MB; change both settings if you intentionally change the limit. `MAX_CONCURRENT_ANALYSES` defaults to 2 and must be positive. `LLM_PROVIDER` defaults to `fake`. For `LLM_PROVIDER=openai`, set both `OPENAI_API_KEY` and an account-supported Structured Outputs model in `OPENAI_MODEL`; there is no default model. Keep `.env` private.

## Run backend

In a terminal with the virtual environment activated:

```sh
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/health`; the response should be `{"status":"ok"}`.

On startup, SQLAlchemy creates missing vacancy, criterion, resume, archive, and analysis tables in the configured SQLite database. Existing local databases gain the separate `resume_archives` table without changing `resumes` columns. This local MVP setup does not migrate existing columns. Schema migrations will require an explicit design in v0.2.

Open `http://127.0.0.1:8000/docs` to exercise the API:

- `GET/POST /vacancies`, `GET/PATCH /vacancies/{id}`
- `GET/POST /vacancies/{id}/criteria`
- `PATCH/DELETE /criteria/{id}`
- `POST/GET /vacancies/{id}/resumes`, `GET /resumes/{id}`; `GET /vacancies/{id}/resumes?include_archived=true` includes archived records
- `POST /resumes/{id}/archive`, `POST /resumes/{id}/restore`, `DELETE /resumes/{id}`
- `POST/GET /vacancies/{id}/analyses`, `GET /analyses/{id}`, `GET /analyses/{id}/results`

Create a vacancy with `title` and `description`, then add criteria with `description` and `priority` (`required` or `preferred`). Criteria have `active` (default `true`) and zero-based `display_order`. If order is omitted, a new criterion is appended after the highest existing order for that vacancy. Lists sort by `display_order`, then ID; changing an order does not renumber other criteria. Vacancy deletion is outside the S01 API.

Upload up to 20 files per request under the `files` multipart field. Each result reports `ready`, `unsupported`, `parse_error`, or `rejected` (for a file over the size limit or a storage failure), plus a `duplicate` flag and safe error message. The multipart parser caps each file as bytes arrive; the service rechecks the limit while copying in 64 KiB chunks. SHA-256 deduplication applies within each vacancy. PDF details include one-based page numbers and extracted page text; DOCX has no reliable page numbers. A scanned PDF without a text layer is `unsupported`; OCR and legacy `.doc` are not implemented. The claimed MIME type is not trusted. Accepted raw uploads use generated names under the ignored `UPLOAD_DIR`; the API never exposes storage paths. Text and source pages are returned only by `GET /resumes/{id}`.

Archiving hides a resume from the default vacancy list and future analyses while retaining its file, extracted text, and all saved findings. `GET /resumes/{id}` and `include_archived=true` expose `archived` and `archived_at`. Reuploading the same SHA returns the existing record with `archived=true`; restore it explicitly to include it in a new run. Archiving during a pending/running run of the same vacancy returns HTTP 409. Repeated archive/restore requests are safe. Physical `DELETE` returns 409 for any resume linked to a saved run, including an archived one; an unlinked archived resume can still be deleted permanently.

For a local synthetic document outside this repository, the upload command is:

```sh
curl -F 'files=@/absolute/path/to/synthetic.pdf' -F 'files=@/absolute/path/to/synthetic.docx' http://127.0.0.1:8000/vacancies/1/resumes
```

## S04 local batch analysis

After creating a vacancy, at least one active criterion, and at least one active ready resume, start an analysis with `POST /vacancies/{id}/analyses` (no body). The endpoint returns HTTP 202 with a run ID and frozen criterion snapshot. `GET /vacancies/{id}/analyses` lists that vacancy's runs newest first, with timestamps and states. Poll `GET /analyses/{run_id}` for run status, counters, provider/model, versions, and timestamps; fetch saved per-resume findings from `GET /analyses/{run_id}/results`. Only one pending or running run may exist per vacancy. When it reaches a terminal state, another run may be started. Invalid uploaded documents are reported as failed within the run; other documents continue. Archived documents remain visible in their old runs.

The default Fake provider works offline. The local dispatcher runs inside the FastAPI process with a shared concurrency limit; it saves each completed resume immediately and retries only transient provider failures up to three times. Incomplete runs become `interrupted` on restart, and can be restarted by submitting a new run. This is not a durable queue: work does not continue while the process is stopped. The API contains evidence for human review; it does not rank candidates or make hiring decisions.

## S03 analysis service

The S03 application service accepts extracted text, optional PDF `source_pages`, and an immutable criterion snapshot. S04 reuses it for each resume. It requires one finding per criterion, checks that each quote is a real text fragment and relevant to the criterion, rejects obvious weak or negative quotes marked `confirmed`, and verifies or derives PDF page numbers from the saved page text. Errors have safe machine-readable codes. It does not turn a provider failure into `not_found`.

The Fake provider is deterministic and offline. It recognizes an exact criterion phrase in synthetic lines such as `Experience: Python`, `Familiar with SQL`, and a pair of contradictory statements. It is intentionally conservative and is not a general natural-language evaluator. Try it directly:

```sh
python - <<'PY'
import asyncio
from datetime import UTC, datetime
from backend.app.core.config import get_settings
from backend.app.llm.contracts import CriterionSnapshot
from backend.app.llm.factory import make_provider
from backend.app.services.analysis import AnalysisService

criterion = CriterionSnapshot(
    id=1, vacancy_id=1, description="Python", priority="required",
    active=True, display_order=0, updated_at=datetime(2026, 10, 29, tzinfo=UTC),
)
service = AnalysisService(make_provider(get_settings()))
result = asyncio.run(service.analyze("Experience: Python", [], [criterion]))
print(result.model_dump_json(indent=2))
PY
```

With the default `LLM_PROVIDER=fake`, this prints a `confirmed` finding with an exact quote and makes no network call. For OpenAI, the adapter uses the official [Responses API Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) helper with Pydantic. Real OpenAI calls send the supplied resume text and criteria to that service; only synthetic or explicitly authorized de-identified data should be used. Model availability and account access have not been verified here, and no paid request is part of the automated tests.

## Run frontend

In a second terminal with the virtual environment activated (and any custom environment loaded):

```sh
python -m streamlit run ui/app.py --server.address 127.0.0.1
```

Open `http://127.0.0.1:8501`. The Russian UI shows backend availability. For a local demo with synthetic files:

1. In **Вакансии**, create a vacancy and select it in the sidebar.
2. In **Критерии**, add required/preferred criteria; edit their active state and display order if needed.
3. In **Резюме**, select up to 20 PDF/DOCX files and click **Загрузить резюме**. Review per-file status, duplicates, and errors. Use **Активные / Архив** to archive or restore a document. **Удалить навсегда** is separate, requires confirmation, and is blocked when the document belongs to analysis history.
4. In **Анализ**, click **Запустить анализ** and use **Обновить** to poll. Choose old runs from **История анализов** by UTC date and status. The percentage measures completed document processing only.
5. In **Результаты**, compare documents side by side in the scrollable fact matrix, filter by factual criterion status, then choose **Детали документа из таблицы** for the exact quote, PDF page, follow-up question, and extracted source text.

The UI keeps the selected vacancy and run across Streamlit reruns. After a browser refresh, select the vacancy and choose a run from its dated history; the latest run is selected automatically. SQLite stores UTC timestamps without timezone metadata, so the UI labels historical dates explicitly as UTC. The Streamlit theme is fixed to a light palette with a larger base font, including when macOS uses Dark Mode. If the API is stopped, refresh the page to see the offline message. See [S05 manual QA](docs/S05_MANUAL_QA.md) for the acceptance flow. Domain CSV export and persistent HR review notes are not implemented in S05.

## Test

```sh
python -m pytest -q
python -m compileall backend ui
```

This repository is for local development with synthetic or authorized de-identified data only. Do not commit keys, `.env`, databases, exports, or real resumes.

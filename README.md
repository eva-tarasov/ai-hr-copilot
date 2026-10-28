# AI HR Copilot

Local development app for the AI HR Copilot. S02 adds bounded PDF/DOCX resume upload and text extraction through FastAPI. Streamlit currently checks backend availability only; analysis features are planned for later phases.

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

`APP_ENV` controls FastAPI debug mode (`development` enables it); `BACKEND_URL` tells Streamlit where to check the API. `DATABASE_URL` defaults to `sqlite:///./data/hr_copilot.sqlite3`; `UPLOAD_DIR` defaults to `uploads`; `MAX_UPLOAD_MB` defaults to 10 per file. `LLM_PROVIDER` defaults to `fake` and is not used by S02. Keep `.env` private.

## Run backend

In a terminal with the virtual environment activated:

```sh
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/health`; the response should be `{"status":"ok"}`.

On startup, SQLAlchemy creates missing vacancy, criterion, and resume tables in the configured SQLite database. This local MVP setup does not migrate existing tables. Schema migrations will require an explicit design in v0.2.

Open `http://127.0.0.1:8000/docs` to exercise the API:

- `GET/POST /vacancies`, `GET/PATCH /vacancies/{id}`
- `GET/POST /vacancies/{id}/criteria`
- `PATCH/DELETE /criteria/{id}`
- `POST/GET /vacancies/{id}/resumes`, `GET /resumes/{id}`

Create a vacancy with `title` and `description`, then add criteria with `description` and `priority` (`required` or `preferred`). Criteria have `active` (default `true`) and zero-based `display_order`. If order is omitted, a new criterion is appended after the highest existing order for that vacancy. Lists sort by `display_order`, then ID; changing an order does not renumber other criteria. Vacancy deletion is outside the S01 API.

Upload up to 20 files per request under the `files` multipart field. Each result reports `ready`, `unsupported`, `parse_error`, or `rejected` (for a file over the size limit or a storage failure), plus a `duplicate` flag and safe error message. The multipart parser caps each file as bytes arrive; the service rechecks the limit while copying in 64 KiB chunks. SHA-256 deduplication applies within each vacancy. PDF details include one-based page numbers and extracted page text; DOCX has no reliable page numbers. A scanned PDF without a text layer is `unsupported`; OCR and legacy `.doc` are not implemented. The claimed MIME type is not trusted. Accepted raw uploads use generated names under the ignored `UPLOAD_DIR`; the API never exposes storage paths. Text and source pages are returned only by `GET /resumes/{id}`.

For a local synthetic document outside this repository, the upload command is:

```sh
curl -F 'files=@/absolute/path/to/synthetic.pdf' -F 'files=@/absolute/path/to/synthetic.docx' http://127.0.0.1:8000/vacancies/1/resumes
```

## Run frontend

In a second terminal with the virtual environment activated (and any custom environment loaded):

```sh
python -m streamlit run ui/app.py --server.address 127.0.0.1
```

Open `http://127.0.0.1:8501`. The page shows whether the backend is available. If the API is stopped, refresh the page to see the offline message.

## Test

```sh
python -m pytest -q
python -m compileall backend ui
```

This repository is for local development with synthetic or authorized de-identified data only. Do not commit keys, `.env`, databases, exports, or real resumes.

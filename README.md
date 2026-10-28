# AI HR Copilot

Local development app for the AI HR Copilot. S01 adds persistent vacancy and criterion management through FastAPI. Streamlit currently checks backend availability only; resume and analysis features are planned for later phases.

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

`APP_ENV` controls FastAPI debug mode (`development` enables it); `BACKEND_URL` tells Streamlit where to check the API. `DATABASE_URL` defaults to `sqlite:///./data/hr_copilot.sqlite3`; `LLM_PROVIDER` defaults to `fake` and is not used by S01. Keep `.env` private.

## Run backend

In a terminal with the virtual environment activated:

```sh
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/health`; the response should be `{"status":"ok"}`.

On startup, SQLAlchemy creates missing vacancy and criterion tables in the configured SQLite database. This local MVP setup does not migrate existing tables. Schema migrations will require an explicit design in v0.2.

Open `http://127.0.0.1:8000/docs` to exercise the S01 API:

- `GET/POST /vacancies`, `GET/PATCH /vacancies/{id}`
- `GET/POST /vacancies/{id}/criteria`
- `PATCH/DELETE /criteria/{id}`

Create a vacancy with `title` and `description`, then add criteria with `description` and `priority` (`required` or `preferred`). Criteria have `active` (default `true`) and zero-based `display_order`. If order is omitted, a new criterion is appended after the highest existing order for that vacancy. Lists sort by `display_order`, then ID; changing an order does not renumber other criteria. Vacancy deletion is outside the S01 API.

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

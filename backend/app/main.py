"""FastAPI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.api.criteria import router as criteria_router
from backend.app.api.health import router as health_router
from backend.app.api.resumes import router as resumes_router
from backend.app.api.vacancies import router as vacancies_router
from backend.app.core.config import get_settings
from backend.app.core.database import create_db_engine, create_schema, create_session_factory
from backend.app.repositories.file_storage import FileStorage
from backend.app.services.errors import NotFoundError


def create_app(
    database_url: str | None = None,
    upload_dir: str | Path | None = None,
    max_upload_bytes: int | None = None,
) -> FastAPI:
    settings = get_settings()
    db_url = database_url or settings.database_url
    size_limit = settings.max_upload_mb * 1024 * 1024 if max_upload_bytes is None else max_upload_bytes
    if size_limit <= 0:
        raise ValueError("max_upload_bytes must be positive")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_db_engine(db_url)
        try:
            create_schema(engine)
            app.state.session_factory = create_session_factory(engine)
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="AI HR Copilot", debug=settings.app_env == "development", lifespan=lifespan
    )
    app.state.file_storage = FileStorage(Path(upload_dir or settings.upload_dir))
    app.state.max_upload_bytes = size_limit

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, error: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    app.include_router(health_router)
    app.include_router(vacancies_router)
    app.include_router(criteria_router)
    app.include_router(resumes_router)
    return app


app = create_app()

"""FastAPI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.api.criteria import router as criteria_router
from backend.app.api.analyses import router as analyses_router
from backend.app.api.health import router as health_router
from backend.app.api.resumes import router as resumes_router
from backend.app.api.vacancies import router as vacancies_router
from backend.app.core.config import get_settings
from backend.app.core.database import create_db_engine, create_schema, create_session_factory
from backend.app.repositories.file_storage import FileStorage
from backend.app.services.errors import ConflictError, InvalidRunError, NotFoundError, ResumeDeleteError
from backend.app.jobs.dispatcher import BatchDispatcher
from backend.app.llm.factory import make_provider
from backend.app.llm.provider import LLMProvider


def create_app(
    database_url: str | None = None,
    upload_dir: str | Path | None = None,
    max_upload_bytes: int | None = None,
    analysis_provider: LLMProvider | None = None,
    max_concurrent_analyses: int | None = None,
) -> FastAPI:
    settings = get_settings()
    db_url = database_url or settings.database_url
    size_limit = settings.max_upload_mb * 1024 * 1024 if max_upload_bytes is None else max_upload_bytes
    if size_limit <= 0:
        raise ValueError("max_upload_bytes must be positive")
    concurrency = settings.max_concurrent_analyses if max_concurrent_analyses is None else max_concurrent_analyses
    if concurrency <= 0:
        raise ValueError("max_concurrent_analyses must be positive")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_db_engine(db_url)
        try:
            create_schema(engine)
            app.state.session_factory = create_session_factory(engine)
            app.state.analysis_provider = analysis_provider or make_provider(settings)
            dispatcher = BatchDispatcher(
                app.state.session_factory, app.state.analysis_provider, concurrency
            )
            dispatcher.recover()
            app.state.batch_dispatcher = dispatcher
            yield
        finally:
            if hasattr(app.state, "batch_dispatcher"):
                await app.state.batch_dispatcher.shutdown()
            engine.dispose()

    app = FastAPI(
        title="AI HR Copilot", debug=settings.app_env == "development", lifespan=lifespan
    )
    app.state.file_storage = FileStorage(Path(upload_dir or settings.upload_dir))
    app.state.max_upload_bytes = size_limit

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, error: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(ConflictError)
    async def conflict(request: Request, error: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(InvalidRunError)
    async def invalid_run(request: Request, error: InvalidRunError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(ResumeDeleteError)
    async def resume_delete_failed(request: Request, error: ResumeDeleteError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "Could not delete resume"})

    app.include_router(health_router)
    app.include_router(vacancies_router)
    app.include_router(criteria_router)
    app.include_router(resumes_router)
    app.include_router(analyses_router)
    return app


app = create_app()

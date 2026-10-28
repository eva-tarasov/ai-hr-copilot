"""FastAPI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.api.criteria import router as criteria_router
from backend.app.api.health import router as health_router
from backend.app.api.vacancies import router as vacancies_router
from backend.app.core.config import get_settings
from backend.app.core.database import create_db_engine, create_schema, create_session_factory
from backend.app.services.errors import NotFoundError


def create_app(database_url: str | None = None) -> FastAPI:
    settings = get_settings()
    db_url = database_url or settings.database_url

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

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, error: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    app.include_router(health_router)
    app.include_router(vacancies_router)
    app.include_router(criteria_router)
    return app


app = create_app()

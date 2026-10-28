"""FastAPI entry point."""

from fastapi import FastAPI

from backend.app.api.health import router as health_router
from backend.app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AI HR Copilot", debug=settings.app_env == "development")
    app.include_router(health_router)
    return app


app = create_app()

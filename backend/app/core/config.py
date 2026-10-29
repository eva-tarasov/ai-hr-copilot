"""Local application settings read from environment variables."""

from dataclasses import dataclass, field
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    database_url: str = "sqlite:///./data/hr_copilot.sqlite3"
    llm_provider: str = "fake"
    openai_model: str | None = None
    openai_api_key: str | None = field(default=None, repr=False)
    max_upload_mb: int = 10
    upload_dir: str = "uploads"


def get_settings() -> Settings:
    max_upload_mb = int(getenv("MAX_UPLOAD_MB", "10"))
    if max_upload_mb <= 0:
        raise ValueError("MAX_UPLOAD_MB must be a positive integer")
    return Settings(
        app_env=getenv("APP_ENV", "local"),
        database_url=getenv("DATABASE_URL", "sqlite:///./data/hr_copilot.sqlite3"),
        llm_provider=getenv("LLM_PROVIDER", "fake"),
        openai_model=getenv("OPENAI_MODEL") or None,
        openai_api_key=getenv("OPENAI_API_KEY") or None,
        max_upload_mb=max_upload_mb,
        upload_dir=getenv("UPLOAD_DIR", "uploads"),
    )

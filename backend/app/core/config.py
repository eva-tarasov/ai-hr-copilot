"""Local application settings read from environment variables."""

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    database_url: str = "sqlite:///./data/hr_copilot.sqlite3"
    llm_provider: str = "fake"


def get_settings() -> Settings:
    return Settings(
        app_env=getenv("APP_ENV", "local"),
        database_url=getenv("DATABASE_URL", "sqlite:///./data/hr_copilot.sqlite3"),
        llm_provider=getenv("LLM_PROVIDER", "fake"),
    )

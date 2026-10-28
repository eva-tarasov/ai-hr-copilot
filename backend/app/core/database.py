"""SQLite engine and session setup for the local MVP."""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models import Base


def create_db_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        raise ValueError("S01 supports SQLite only")
    if url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)

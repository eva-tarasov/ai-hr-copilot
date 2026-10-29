"""Isolated SQLite-backed API client for all tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite:///{tmp_path / 'test.sqlite3'}"
    with TestClient(create_app(database_url=database_url, upload_dir=tmp_path / "uploads")) as test_client:
        yield test_client

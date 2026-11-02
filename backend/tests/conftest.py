from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app
from app.repository import SQLiteSessionRepository
from app.routers import sessions


@pytest.fixture
def repository(tmp_path: Path) -> Iterator[SQLiteSessionRepository]:
    repo = SQLiteSessionRepository(tmp_path / "test.db")
    app.dependency_overrides[sessions.get_repository] = lambda: repo
    yield repo
    app.dependency_overrides[sessions.get_repository] = (
        lambda: main_module.repository
    )


@pytest.fixture
def client(repository: SQLiteSessionRepository) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client

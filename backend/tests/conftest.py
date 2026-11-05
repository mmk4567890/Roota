from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app
from app.parser.fake import KeywordParser
from app.repository import SQLiteSessionRepository
from app.retrieval.embeddings import FakeEmbeddingFunction
from app.retrieval.store import ManualStore
from app.routers import docs, sessions


@pytest.fixture
def repository(tmp_path: Path) -> Iterator[SQLiteSessionRepository]:
    repo = SQLiteSessionRepository(tmp_path / "test.db")
    app.dependency_overrides[sessions.get_repository] = lambda: repo
    yield repo
    app.dependency_overrides[sessions.get_repository] = (
        lambda: main_module.repository
    )


@pytest.fixture
def client(
    repository: SQLiteSessionRepository,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    # Tests must never call the real Anthropic API or download embedding models.
    monkeypatch.setenv("ROOTA_PARSER", "keyword")
    monkeypatch.setenv("ROOTA_CHROMA_DIR", str(tmp_path / "chroma-app"))
    monkeypatch.setenv("ROOTA_DOCS_DB_PATH", str(tmp_path / "docs-app.db"))
    monkeypatch.setattr(
        "app.retrieval.store.default_embedding_function",
        lambda: FakeEmbeddingFunction(),
    )
    store = ManualStore(
        chroma_dir=tmp_path / "chroma-client",
        docs_db_path=tmp_path / "docs-client.db",
        embedding_function=FakeEmbeddingFunction(),
    )
    app.dependency_overrides[sessions.get_parser] = lambda: KeywordParser()
    app.dependency_overrides[docs.get_manual_store] = lambda: store
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(sessions.get_parser, None)
        app.dependency_overrides.pop(docs.get_manual_store, None)

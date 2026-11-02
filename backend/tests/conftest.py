from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app, repository


@pytest.fixture(autouse=True)
def clear_repository() -> Iterator[None]:
    repository.clear()
    yield
    repository.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    # The context manager runs the lifespan handler, which loads the fault graphs.
    with TestClient(app) as test_client:
        yield test_client

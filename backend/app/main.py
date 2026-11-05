from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.parser.factory import create_parser_from_env
from app.repository import SQLiteSessionRepository, default_db_path
from app.retrieval.store import ManualStore
from app.routers import docs, faults, sessions

repository = SQLiteSessionRepository(default_db_path())


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncIterator[None]:
    load_graphs(DEFAULT_GRAPHS_DIR)
    # Built at startup so ROOTA_PARSER=anthropic without a key stops the server
    # before it accepts requests. Stored on app.state (not in
    # dependency_overrides) so startup never replaces a test's override.
    app_.state.parser = create_parser_from_env()
    app_.state.manual_store = ManualStore()
    yield


# OpenAPI UI moves off /docs so GET /docs can list ingested manuals.
app = FastAPI(
    title="Roota",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(sessions.router)
app.include_router(faults.router)
app.include_router(docs.router)
app.dependency_overrides[sessions.get_repository] = lambda: repository


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

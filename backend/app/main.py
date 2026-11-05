from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.parser.factory import create_parser_from_env
from app.repository import SQLiteSessionRepository, default_db_path
from app.routers import faults, sessions

repository = SQLiteSessionRepository(default_db_path())
# Built at import / lifespan so ROOTA_PARSER=anthropic without a key fails at
# startup, not on the first observation request.
parser = create_parser_from_env()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    load_graphs(DEFAULT_GRAPHS_DIR)
    # Re-resolve in case env changed between import and startup in tests.
    global parser
    parser = create_parser_from_env()
    app.dependency_overrides[sessions.get_parser] = lambda: parser
    yield


app = FastAPI(title="Roota", version="0.1.0", lifespan=lifespan)
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
app.dependency_overrides[sessions.get_repository] = lambda: repository
app.dependency_overrides[sessions.get_parser] = lambda: parser


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

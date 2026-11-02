from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.repository import InMemorySessionRepository
from app.routers import faults, sessions

repository = InMemorySessionRepository()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    load_graphs(DEFAULT_GRAPHS_DIR)
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

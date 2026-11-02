from fastapi import FastAPI

from app.repository import InMemorySessionRepository
from app.routers import sessions

repository = InMemorySessionRepository()

app = FastAPI(title="Routa", version="0.1.0")
app.include_router(sessions.router)
app.dependency_overrides[sessions.get_repository] = lambda: repository


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

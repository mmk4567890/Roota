from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import ObservationCreate, Session, SessionCreate
from app.repository import SessionRepository

router = APIRouter(tags=["sessions"])


def get_repository() -> SessionRepository:
    """Overridden in main with the shared in-memory repository."""
    raise RuntimeError("Repository dependency was not configured")


@router.post(
    "/sessions",
    response_model=Session,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    payload: SessionCreate,
    repository: SessionRepository = Depends(get_repository),
) -> Session:
    return repository.create(payload)


@router.get("/sessions/{session_id}", response_model=Session)
def get_session(
    session_id: UUID,
    repository: SessionRepository = Depends(get_repository),
) -> Session:
    session = repository.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return session


@router.post(
    "/sessions/{session_id}/observations",
    response_model=Session,
    status_code=status.HTTP_201_CREATED,
)
def add_observation(
    session_id: UUID,
    payload: ObservationCreate,
    repository: SessionRepository = Depends(get_repository),
) -> Session:
    session = repository.add_observation(session_id, payload)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return session

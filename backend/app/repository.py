from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

from app.models import Observation, ObservationCreate, Session, SessionCreate


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionRepository(Protocol):
    """Storage interface for troubleshooting sessions."""

    def create(self, payload: SessionCreate) -> Session:
        """Create and store a new session."""

    def get(self, session_id: UUID) -> Session | None:
        """Return a session by id, or None if it does not exist."""

    def add_observation(
        self, session_id: UUID, payload: ObservationCreate
    ) -> Session | None:
        """Append an observation to a session. Returns None if missing."""


class InMemorySessionRepository:
    """Process-local session store. State is lost on restart and not shared across workers."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}
        self._lock = Lock()

    def create(self, payload: SessionCreate) -> Session:
        now = _utc_now()
        session = Session(
            id=uuid4(),
            equipment_name=payload.equipment_name,
            fault_description=payload.fault_description,
            observations=[],
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._sessions[session.id] = session
            return session.model_copy(deep=True)

    def get(self, session_id: UUID) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            return session.model_copy(deep=True)

    def add_observation(
        self, session_id: UUID, payload: ObservationCreate
    ) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            now = _utc_now()
            observation = Observation(
                id=uuid4(),
                question=payload.question,
                answer=payload.answer,
                created_at=now,
            )
            updated = session.model_copy(
                update={
                    "observations": [*session.observations, observation],
                    "updated_at": now,
                }
            )
            self._sessions[session_id] = updated
            return updated.model_copy(deep=True)

    def clear(self) -> None:
        """Remove all sessions. Intended for tests."""
        with self._lock:
            self._sessions.clear()

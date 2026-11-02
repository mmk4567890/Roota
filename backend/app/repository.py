from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.models import Event


class SessionClosedError(Exception):
    """Raised when appending to a session that already has a closed event."""


class EventAlreadyUndoneError(Exception):
    """Raised when an undo targets an event that already has an undo."""


def default_db_path() -> Path:
    configured = os.environ.get("ROOTA_DB_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "data" / "roota.db"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SessionRecord:
    id: UUID
    fault_id: str
    equipment_label: str
    created_at: datetime


class SessionRepository(Protocol):
    """Append-only storage for fault-isolation sessions and their events."""

    def create_session(self, fault_id: str, equipment_label: str) -> SessionRecord:
        """Create a session row and return it."""

    def get_session(self, session_id: UUID) -> SessionRecord | None:
        """Return a session, or None if it does not exist."""

    def list_events(self, session_id: UUID) -> list[Event]:
        """Return events for a session in seq order."""

    def append_event(
        self,
        session_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> Event:
        """Append an event with the next sequential seq for the session."""


class SQLiteSessionRepository:
    """SQLite-backed session store. Events are append-only."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path is not None else default_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        # sqlite3's own context manager only commits/rolls back; it never closes the
        # connection. Close explicitly so no handle (and Windows file lock) leaks.
        connection = sqlite3.connect(self._db_path, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    fault_id TEXT NOT NULL,
                    equipment_label TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (session_id, seq),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
                """
            )

    def create_session(self, fault_id: str, equipment_label: str) -> SessionRecord:
        session_id = uuid4()
        created_at = _utc_now()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, fault_id, equipment_label, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(session_id),
                    fault_id,
                    equipment_label,
                    created_at.isoformat(),
                ),
            )
        return SessionRecord(
            id=session_id,
            fault_id=fault_id,
            equipment_label=equipment_label,
            created_at=created_at,
        )

    def get_session(self, session_id: UUID) -> SessionRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, fault_id, equipment_label, created_at
                FROM sessions
                WHERE id = ?
                """,
                (str(session_id),),
            ).fetchone()
        if row is None:
            return None
        return SessionRecord(
            id=UUID(row["id"]),
            fault_id=row["fault_id"],
            equipment_label=row["equipment_label"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_events(self, session_id: UUID) -> list[Event]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, session_id, seq, type, payload, created_at
                FROM events
                WHERE session_id = ?
                ORDER BY seq ASC
                """,
                (str(session_id),),
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    def append_event(
        self,
        session_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> Event:
        created_at = _utc_now()
        payload_json = json.dumps(payload)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                session_row = connection.execute(
                    "SELECT id FROM sessions WHERE id = ?",
                    (str(session_id),),
                ).fetchone()
                if session_row is None:
                    raise KeyError(f"session {session_id} not found")
                # Guards run inside the write transaction so concurrent requests
                # cannot both pass a check made before it.
                if connection.execute(
                    "SELECT 1 FROM events WHERE session_id = ? AND type = 'closed'",
                    (str(session_id),),
                ).fetchone():
                    raise SessionClosedError(f"session {session_id} is closed")
                if event_type == "undo" and connection.execute(
                    """
                    SELECT 1 FROM events
                    WHERE session_id = ? AND type = 'undo'
                      AND json_extract(payload, '$.target_event_id') = ?
                    """,
                    (str(session_id), payload["target_event_id"]),
                ).fetchone():
                    raise EventAlreadyUndoneError(
                        f"event {payload['target_event_id']} is already undone"
                    )

                seq = connection.execute(
                    """
                    SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq
                    FROM events
                    WHERE session_id = ?
                    """,
                    (str(session_id),),
                ).fetchone()["next_seq"]

                cursor = connection.execute(
                    """
                    INSERT INTO events (session_id, seq, type, payload, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(session_id),
                        seq,
                        event_type,
                        payload_json,
                        created_at.isoformat(),
                    ),
                )
                event_id = int(cursor.lastrowid)
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

        return Event(
            id=event_id,
            session_id=session_id,
            seq=seq,
            type=event_type,  # type: ignore[arg-type]
            payload=payload,
            created_at=created_at,
        )


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=int(row["id"]),
        session_id=UUID(row["session_id"]),
        seq=int(row["seq"]),
        type=row["type"],
        payload=json.loads(row["payload"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )

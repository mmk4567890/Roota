from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.engine.engine import DiagnosticState
from app.parser.base import ParseResult

MAX_OBSERVATION_TEXT_LENGTH = 2000


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fault_id: str = Field(..., min_length=1)
    equipment_label: str = Field(..., min_length=1)
    initial_facts: dict[str, Any] = Field(default_factory=dict)

    @field_validator("fault_id", "equipment_label")
    @classmethod
    def strip_and_reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class FactsReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: dict[str, Any]
    check_id: str | None = None


class ObservationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=MAX_OBSERVATION_TEXT_LENGTH)
    check_id: str | None = None

    @field_validator("text")
    @classmethod
    def strip_and_reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class UndoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: int


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    session_id: UUID
    seq: int
    type: Literal["facts_reported", "observation", "undo", "closed"]
    payload: dict[str, Any]
    created_at: datetime


class SessionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    fault_id: str
    equipment_label: str
    status: Literal["active", "closed"]
    created_at: datetime
    events: list[Event]
    state: DiagnosticState


class ObservationResponse(SessionView):
    """Session view plus the parse result for UI feedback."""

    model_config = ConfigDict(extra="forbid")

    parse: ParseResult
    message: str | None = None

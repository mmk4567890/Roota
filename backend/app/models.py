from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SessionCreate(BaseModel):
    equipment_name: str = Field(..., min_length=1)
    fault_description: str = Field(..., min_length=1)

    @field_validator("equipment_name", "fault_description")
    @classmethod
    def strip_and_reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ObservationCreate(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)

    @field_validator("question", "answer")
    @classmethod
    def strip_and_reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class Observation(BaseModel):
    id: UUID
    question: str
    answer: str
    created_at: datetime


class Session(BaseModel):
    id: UUID
    equipment_name: str
    fault_description: str
    observations: list[Observation]
    created_at: datetime
    updated_at: datetime

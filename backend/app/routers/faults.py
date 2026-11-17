from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.engine.schema import FaultGraph
from app.graphs.loader import get_graphs

router = APIRouter(tags=["faults"])


class FieldInfo(BaseModel):
    """Field spec for the technician facts form (mirrors graph FieldSpec)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    type: Literal["enum", "number", "boolean"]
    values: list[str] | None = None
    value_labels: dict[str, str] | None = None
    unit: str | None = None
    description: str
    ask: str


class FaultInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fault_id: str
    display_name: str
    fault_codes: list[str]
    description: str
    fields: list[FieldInfo]


@router.get("/faults", response_model=list[FaultInfo])
def list_faults(
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
) -> list[FaultInfo]:
    return [
        FaultInfo(
            fault_id=graph.fault_id,
            display_name=graph.display_name,
            fault_codes=list(graph.fault_codes),
            description=graph.description,
            fields=[
                FieldInfo(
                    name=field.name,
                    label=field.label,
                    type=field.type,
                    values=list(field.values) if field.values is not None else None,
                    value_labels=(
                        dict(field.value_labels) if field.value_labels is not None else None
                    ),
                    unit=field.unit,
                    description=field.description,
                    ask=field.ask,
                )
                for field in graph.fields
            ],
        )
        for graph in graphs.values()
    ]

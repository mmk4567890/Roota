from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from app.engine.schema import FaultGraph


class ParseError(Exception):
    """Raised when parser output is structurally broken or contradictory.

    The observations route maps this to HTTP 502 and does not record an event.
    """


class RejectedValue(BaseModel):
    """A value the parser proposed that validation refused to keep as a fact."""

    model_config = ConfigDict(extra="forbid")

    field: str
    value: Any
    reason: str


class ParseResult(BaseModel):
    """Structured extraction from a technician observation.

    ``extracted`` holds accepted field values. ``unclear_fields`` lists fields
    the text mentioned but could not resolve (replay stores them as "unclear").
    ``rejected`` names every bad proposal so nothing is silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    extracted: dict[str, Any]
    unclear_fields: list[str]
    rejected: list[RejectedValue]
    notes: str


class ObservationParser(Protocol):
    """Translate free-text observations into field values for a fault graph."""

    def parse(
        self,
        text: str,
        graph: FaultGraph,
        expected_fields: list[str],
    ) -> ParseResult:
        """Extract field values from ``text``.

        ``expected_fields`` are the fields collected by the check that was just
        recommended; the parser may also extract any other graph field the
        technician volunteers.
        """
        ...

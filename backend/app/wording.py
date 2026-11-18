"""Plain-language wording for cause statuses and reasons.

Pure functions over a fault graph and an engine result — no I/O, no LLM. The
words come from the graph (``value_phrases``, ``unsure_phrase``); this module
only decides which facts to mention and how to join them.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.engine.engine import CauseStatus, Truth, evaluate_condition
from app.engine.schema import (
    UNCLEAR,
    AllCondition,
    AnyCondition,
    Cause,
    Condition,
    FaultGraph,
    FieldCondition,
    FieldSpec,
    format_fact,
)

UNSURE_NOTE = "(technician wasn't sure)"
NOT_CHECKED = "Not checked"

_STATUS_LABELS = {
    "confirmed": "Confirmed",
    "ruled_out": "Ruled out",
    "contradiction": "Contradiction",
    "open": "Open",
    "inconclusive": "Inconclusive",
}


def cause_status_label(status: str, *, outcome_reached: bool) -> str:
    """Badge text. Once the session has an outcome, open causes were never checked."""
    if status == "open" and outcome_reached:
        return NOT_CHECKED
    return _STATUS_LABELS[status]


def fact_phrase(spec: FieldSpec, value: Any) -> str:
    """``Heatsink was clean``; fields without phrases read ``Label: value``."""
    if spec.value_phrases is not None and isinstance(value, str):
        return spec.value_phrases[value]
    return format_fact(spec, value)


def unsure_phrase(spec: FieldSpec) -> str:
    """``air flow not confirmed`` for a field answered "unclear"."""
    if spec.unsure_phrase is not None:
        return spec.unsure_phrase
    return f"{spec.label} not confirmed"


def unsure_subject(spec: FieldSpec) -> str:
    """``the air flow`` — what the technician wasn't sure about."""
    if spec.unsure_subject is not None:
        return spec.unsure_subject
    return spec.label.lower()


def cause_reason(
    graph: FaultGraph, cause: CauseStatus, facts: dict[str, Any]
) -> str | None:
    """One plain phrase naming the checks behind a cause's status.

    ``None`` for an open cause: nothing has decided it yet.
    """
    if not cause.because:
        return None
    field_by_name = {field.name: field for field in graph.fields}
    answered = [name for name in cause.because if facts.get(name) not in (None, UNCLEAR)]
    unsure = [name for name in cause.because if facts.get(name) == UNCLEAR]

    if cause.status == "ruled_out":
        graph_cause = _graph_cause(graph, cause.cause_id)
        pointing = _fields_pointing_to_cause(graph_cause, facts)
        towards = [name for name in answered if name in pointing]
        against = [name for name in answered if name not in pointing]
        if towards and against:
            return (
                _join(field_by_name, towards, facts)
                + ", but "
                + _lower_first(_join(field_by_name, against, facts))
            )

    phrases = [fact_phrase(field_by_name[name], facts[name]) for name in answered]
    if unsure:
        unsure_bits = "; ".join(unsure_phrase(field_by_name[name]) for name in unsure)
        phrases.append(f"{unsure_bits} {UNSURE_NOTE}")
    text = "; ".join(phrases)
    if cause.status == "contradiction":
        return f"Answers conflict: {_lower_first(text)}"
    return _upper_first(text)


def _join(field_by_name: dict[str, FieldSpec], names: list[str], facts: dict[str, Any]) -> str:
    return "; ".join(fact_phrase(field_by_name[name], facts[name]) for name in names)


def _graph_cause(graph: FaultGraph, cause_id: str) -> Cause:
    return next(cause for cause in graph.causes if cause.id == cause_id)


def _fields_pointing_to_cause(cause: Cause, facts: dict[str, Any]) -> set[str]:
    """Fields whose reported value satisfies part of the cause's confirm rule."""
    if cause.confirmed_when is None:
        return set()
    return {
        leaf.field
        for leaf in _leaves(cause.confirmed_when)
        if evaluate_condition(leaf, facts)[0] is Truth.TRUE
    }


def _leaves(condition: Condition) -> Iterator[FieldCondition]:
    if isinstance(condition, AllCondition):
        for child in condition.all:
            yield from _leaves(child)
    elif isinstance(condition, AnyCondition):
        for child in condition.any:
            yield from _leaves(child)
    else:
        yield condition


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]

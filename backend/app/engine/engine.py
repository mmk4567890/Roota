from __future__ import annotations

import math
from collections.abc import Iterable
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.engine.schema import (
    UNCLEAR,
    AllCondition,
    AnyCondition,
    Cause,
    Check,
    Condition,
    FaultGraph,
    FieldCondition,
    FieldSpec,
    Source,
    format_fact,
)

# Stored on inconclusive causes / escalation when the technician answered "unclear".
UNCLEAR_REASON = "Technician wasn't sure"


class Truth(Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class CauseStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause_id: str
    name: str
    status: Literal[
        "confirmed", "ruled_out", "contradiction", "open", "inconclusive"
    ]
    because: list[str]
    # True when promote_when holds; the engine also lifts these earlier in
    # investigation order. Exposed so the UI can mark them without re-evaluating.
    promoted: bool = False


class Evidence(BaseModel):
    """Verbatim manual passage attached by the API layer (never by the engine)."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    page: int
    section: str
    text: str
    kind: Literal["cited", "related"]


class NextAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["check", "need_info", "root_cause", "escalate"]
    message: str
    check: Check | None = None
    cause_id: str | None = None
    fields: list[str] | None = None
    source: Source | None = None
    # Populated only by the API layer after evaluate(); the engine leaves these None.
    evidence: list[Evidence] | None = None
    evidence_status: Literal["attached", "no_manual", "unavailable"] | None = None
    evidence_error: str | None = None


class DiagnosticState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fault_id: str
    facts: dict[str, Any]
    causes: list[CauseStatus]
    checks_completed: list[str]
    next_action: NextAction


def evaluate(graph: FaultGraph, facts: dict[str, Any]) -> DiagnosticState:
    """Deterministic diagnostic decision over a fault graph and known facts."""
    validate_facts(graph, facts)
    # Graph field order, not caller order, so the same facts always serialise identically.
    facts_snapshot = {field.name: facts[field.name] for field in graph.fields if field.name in facts}

    field_by_name = {field.name: field for field in graph.fields}
    check_by_id = {check.id: check for check in graph.checks}

    status_by_id: dict[str, CauseStatus] = {}
    for cause in sorted(graph.causes, key=lambda item: item.priority):
        status_by_id[cause.id] = _cause_status(cause, facts_snapshot, check_by_id)

    # Non-open causes keep priority order; open causes use investigation order
    # (promoted first) so the UI can render groups without reordering.
    non_open = [
        status_by_id[cause.id]
        for cause in sorted(graph.causes, key=lambda item: item.priority)
        if status_by_id[cause.id].status != "open"
    ]
    open_ordered = [
        status_by_id[cause.id]
        for cause in _ordered_open_causes(graph, facts_snapshot, status_by_id)
    ]
    cause_statuses = non_open + open_ordered

    checks_completed = [
        check.id
        for check in graph.checks
        if all(
            _is_answered(facts_snapshot, field_name) for field_name in check.collects
        )
    ]

    next_action = _decide_next_action(
        graph=graph,
        facts=facts_snapshot,
        cause_statuses=cause_statuses,
        status_by_id=status_by_id,
        check_by_id=check_by_id,
        field_by_name=field_by_name,
    )

    return DiagnosticState(
        fault_id=graph.fault_id,
        facts=facts_snapshot,
        causes=cause_statuses,
        checks_completed=checks_completed,
        next_action=next_action,
    )


def evaluate_condition(
    condition: Condition, facts: dict[str, Any]
) -> tuple[Truth, list[str]]:
    """Evaluate a condition with three-valued logic.

    Returns the truth value and the deterministic list of field names that
    justified a TRUE result (empty when not TRUE).
    """
    if isinstance(condition, AllCondition):
        child_results = [evaluate_condition(child, facts) for child in condition.all]
        if any(truth is Truth.FALSE for truth, _ in child_results):
            return Truth.FALSE, []
        if any(truth is Truth.UNKNOWN for truth, _ in child_results):
            return Truth.UNKNOWN, []
        because = _unique_sorted(
            field for _, fields in child_results for field in fields
        )
        return Truth.TRUE, because

    if isinstance(condition, AnyCondition):
        child_results = [evaluate_condition(child, facts) for child in condition.any]
        true_fields = [
            fields for truth, fields in child_results if truth is Truth.TRUE
        ]
        if true_fields:
            because = _unique_sorted(field for fields in true_fields for field in fields)
            return Truth.TRUE, because
        if any(truth is Truth.UNKNOWN for truth, _ in child_results):
            return Truth.UNKNOWN, []
        return Truth.FALSE, []

    return _evaluate_leaf(condition, facts)


def _evaluate_leaf(
    condition: FieldCondition, facts: dict[str, Any]
) -> tuple[Truth, list[str]]:
    if condition.field not in facts:
        return Truth.UNKNOWN, []

    actual = facts[condition.field]
    expected = condition.value
    op = condition.op

    # "unclear" is a reported answer, not a missing fact. It never equals a
    # concrete confirm/rule-out value (eq/in/comparisons → FALSE) and is not
    # equal under ne → TRUE, so sibling fields can still decide the cause.
    if actual == UNCLEAR:
        if op == "ne":
            return Truth.TRUE, [condition.field]
        return Truth.FALSE, []

    if op == "eq":
        matched = actual == expected
    elif op == "ne":
        matched = actual != expected
    elif op == "in":
        assert isinstance(expected, list)
        matched = actual in expected
    elif op == "gt":
        matched = actual > expected  # type: ignore[operator]
    elif op == "gte":
        matched = actual >= expected  # type: ignore[operator]
    elif op == "lt":
        matched = actual < expected  # type: ignore[operator]
    elif op == "lte":
        matched = actual <= expected  # type: ignore[operator]
    else:  # pragma: no cover - schema restricts ops
        raise ValueError(f"unsupported op '{op}'")

    if matched:
        return Truth.TRUE, [condition.field]
    return Truth.FALSE, []


def _cause_status(
    cause: Cause,
    facts: dict[str, Any],
    check_by_id: dict[str, Check],
) -> CauseStatus:
    confirmed = Truth.UNKNOWN
    confirmed_because: list[str] = []
    ruled_out = Truth.UNKNOWN
    ruled_out_because: list[str] = []

    for name, condition in cause.conditions():
        truth, because = evaluate_condition(condition, facts)
        if name == "confirmed_when":
            confirmed, confirmed_because = truth, because
        elif name == "ruled_out_when":
            ruled_out, ruled_out_because = truth, because

    promoted = _is_promoted(cause, facts)

    if confirmed is Truth.TRUE and ruled_out is Truth.TRUE:
        return CauseStatus(
            cause_id=cause.id,
            name=cause.name,
            status="contradiction",
            because=_unique_sorted(confirmed_because + ruled_out_because),
            promoted=promoted,
        )
    if confirmed is Truth.TRUE:
        return CauseStatus(
            cause_id=cause.id,
            name=cause.name,
            status="confirmed",
            because=confirmed_because,
            promoted=promoted,
        )
    if ruled_out is Truth.TRUE:
        return CauseStatus(
            cause_id=cause.id,
            name=cause.name,
            status="ruled_out",
            because=ruled_out_because,
            promoted=promoted,
        )

    collectable = [
        field_name
        for check_id in cause.checks
        for field_name in check_by_id[check_id].collects
    ]
    # Unclear answers count as answered but do not confirm or rule out. Keep the
    # cause open while other collectable fields are still missing so later
    # checks can still confirm or rule it out. Only when every collectable
    # field is answered and neither condition holds → inconclusive.
    if collectable and all(
        _is_answered(facts, field_name) for field_name in collectable
    ):
        return CauseStatus(
            cause_id=cause.id,
            name=cause.name,
            status="inconclusive",
            because=_unique_sorted(collectable),
            promoted=promoted,
        )

    return CauseStatus(
        cause_id=cause.id,
        name=cause.name,
        status="open",
        because=[],
        promoted=promoted,
    )


def _decide_next_action(
    *,
    graph: FaultGraph,
    facts: dict[str, Any],
    cause_statuses: list[CauseStatus],
    status_by_id: dict[str, CauseStatus],
    check_by_id: dict[str, Check],
    field_by_name: dict[str, FieldSpec],
) -> NextAction:
    contradictions = [item for item in cause_statuses if item.status == "contradiction"]
    if contradictions:
        cause = contradictions[0]
        conflict = (
            _format_reason_bits(cause.because, facts, field_by_name)
            if cause.because
            else "unknown facts"
        )
        return NextAction(
            type="escalate",
            cause_id=cause.cause_id,
            fields=list(cause.because),
            message=(
                f"Contradiction on cause '{cause.name}': "
                f"confirmed and ruled out by facts [{conflict}]."
            ),
        )

    confirmed = [item for item in cause_statuses if item.status == "confirmed"]
    if confirmed:
        # cause_statuses already ordered by priority (ascending).
        cause_status = confirmed[0]
        cause = next(item for item in graph.causes if item.id == cause_status.cause_id)
        return NextAction(
            type="root_cause",
            cause_id=cause.id,
            message=cause.corrective_action,
            source=cause.action_source,
        )

    open_causes = _ordered_open_causes(graph, facts, status_by_id)
    if not open_causes:
        return _escalate_exhausted(cause_statuses, facts, field_by_name)

    current = open_causes[0]
    for check_id in current.checks:
        check = check_by_id[check_id]
        # Unanswered only — "unclear" counts as answered and marks the cause
        # inconclusive above, so we never re-ask via need_info.
        unknown_fields = [
            field_name
            for field_name in check.collects
            if not _is_answered(facts, field_name)
        ]
        if not unknown_fields:
            continue

        return NextAction(
            type="check",
            check=check,
            cause_id=current.id,
            fields=unknown_fields,
            message=check.instruction,
            source=check.source,
        )

    # An open cause should have been marked inconclusive once its checks are
    # complete; reaching here means the graph left a gap — escalate that cause.
    return NextAction(
        type="escalate",
        cause_id=current.id,
        message=(
            f"The documented checks for {current.name} are complete but do not resolve it."
        ),
    )


def _escalate_exhausted(
    cause_statuses: list[CauseStatus],
    facts: dict[str, Any],
    field_by_name: dict[str, FieldSpec],
) -> NextAction:
    """Escalate when nothing remains open and nothing is confirmed."""
    inconclusive = [item for item in cause_statuses if item.status == "inconclusive"]
    if not inconclusive:
        return NextAction(
            type="escalate",
            message="All documented causes for this fault have been ruled out.",
        )

    parts: list[str] = []
    for item in inconclusive:
        why = _format_reason_bits(item.because, facts, field_by_name)
        if why:
            parts.append(f"{item.name} ({why})")
        else:
            parts.append(item.name)

    cause_id = inconclusive[0].cause_id if len(inconclusive) == 1 else None
    return NextAction(
        type="escalate",
        cause_id=cause_id,
        message=(
            "All documented causes are ruled out or inconclusive; none confirmed. "
            f"Inconclusive: {'; '.join(parts)}."
        ),
    )


def _format_reason_bits(
    fields: list[str],
    facts: dict[str, Any],
    field_by_name: dict[str, FieldSpec],
) -> str:
    """User-facing reason fragments: ``Fan status: Noisy`` or unclear wording."""
    bits: list[str] = []
    for field_name in fields:
        if field_name not in facts:
            continue
        value = facts[field_name]
        if value == UNCLEAR:
            bits.append(UNCLEAR_REASON)
            continue
        spec = field_by_name.get(field_name)
        if spec is None:
            raise ValueError(f"unknown field '{field_name}' in cause because")
        bits.append(format_fact(spec, value))
    return ", ".join(bits)


def _ordered_open_causes(
    graph: FaultGraph,
    facts: dict[str, Any],
    status_by_id: dict[str, CauseStatus],
) -> list[Cause]:
    open_causes = [
        cause
        for cause in graph.causes
        if status_by_id[cause.id].status == "open"
    ]

    promoted: list[Cause] = []
    remainder: list[Cause] = []
    for cause in open_causes:
        if _is_promoted(cause, facts):
            promoted.append(cause)
        else:
            remainder.append(cause)

    promoted.sort(key=lambda cause: cause.priority)
    remainder.sort(key=lambda cause: cause.priority)
    return promoted + remainder


def _is_promoted(cause: Cause, facts: dict[str, Any]) -> bool:
    if cause.promote_when is None:
        return False
    truth, _ = evaluate_condition(cause.promote_when, facts)
    return truth is Truth.TRUE


def _is_answered(facts: dict[str, Any], field_name: str) -> bool:
    """True when the technician has reported the field, including unclear."""
    return field_name in facts


def _unique_sorted(fields: Iterable[str]) -> list[str]:
    return sorted(set(fields))


def _is_finite(value: int | float) -> bool:
    # math.isfinite converts ints to float and raises OverflowError for ones
    # beyond float range (e.g. a 400-digit JSON integer); those are rejected
    # like infinity rather than surfacing as a 500.
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_facts(graph: FaultGraph, facts: dict[str, Any]) -> None:
    field_by_name = {field.name: field for field in graph.fields}
    for field_name, value in facts.items():
        field = field_by_name.get(field_name)
        if field is None:
            raise ValueError(f"unknown field '{field_name}'")
        if value == UNCLEAR:
            continue
        if field.type == "enum":
            if not isinstance(value, str) or value not in (field.values or []):
                raise ValueError(
                    f"invalid value for field '{field_name}': expected one of "
                    f"{field.values}, got {value!r}"
                )
        elif field.type == "number":
            # NaN and infinity compare false/true against every threshold and would
            # silently skew cause statuses, so only finite numbers are facts.
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not _is_finite(value)
            ):
                raise ValueError(
                    f"invalid value for field '{field_name}': expected a finite number, "
                    f"got {value!r}"
                )
        elif field.type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(
                    f"invalid value for field '{field_name}': expected true or false, "
                    f"got {value!r}"
                )

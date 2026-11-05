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
)


class Truth(Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class CauseStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause_id: str
    name: str
    status: Literal["confirmed", "ruled_out", "contradiction", "open"]
    because: list[str]


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
    # Populated only by the API layer after evaluate(); the engine leaves this None.
    evidence: list[Evidence] | None = None


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

    cause_statuses: list[CauseStatus] = []
    status_by_id: dict[str, CauseStatus] = {}
    for cause in sorted(graph.causes, key=lambda item: item.priority):
        status = _cause_status(cause, facts_snapshot)
        cause_statuses.append(status)
        status_by_id[cause.id] = status

    checks_completed = [
        check.id
        for check in graph.checks
        if all(_is_known(facts_snapshot, field_name) for field_name in check.collects)
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
    if not _is_known(facts, condition.field):
        return Truth.UNKNOWN, []

    actual = facts[condition.field]
    expected = condition.value
    op = condition.op

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


def _cause_status(cause: Cause, facts: dict[str, Any]) -> CauseStatus:
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

    if confirmed is Truth.TRUE and ruled_out is Truth.TRUE:
        return CauseStatus(
            cause_id=cause.id,
            name=cause.name,
            status="contradiction",
            because=_unique_sorted(confirmed_because + ruled_out_because),
        )
    if confirmed is Truth.TRUE:
        return CauseStatus(
            cause_id=cause.id,
            name=cause.name,
            status="confirmed",
            because=confirmed_because,
        )
    if ruled_out is Truth.TRUE:
        return CauseStatus(
            cause_id=cause.id,
            name=cause.name,
            status="ruled_out",
            because=ruled_out_because,
        )
    return CauseStatus(
        cause_id=cause.id,
        name=cause.name,
        status="open",
        because=[],
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
        conflict = ", ".join(cause.because) if cause.because else "unknown facts"
        return NextAction(
            type="escalate",
            cause_id=cause.cause_id,
            fields=list(cause.because),
            message=(
                f"Contradiction on cause '{cause.name}' "
                f"({cause.cause_id}): confirmed and ruled out by facts [{conflict}]."
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
        return NextAction(
            type="escalate",
            message="All documented causes for this fault have been ruled out.",
        )

    current = open_causes[0]
    for check_id in current.checks:
        check = check_by_id[check_id]
        unknown_fields = [
            field_name
            for field_name in check.collects
            if not _is_known(facts, field_name)
        ]
        if not unknown_fields:
            continue

        unclear_fields = [
            field_name
            for field_name in unknown_fields
            if facts.get(field_name) == UNCLEAR
        ]
        if unclear_fields:
            primary = unclear_fields[0]
            return NextAction(
                type="need_info",
                cause_id=current.id,
                fields=unclear_fields,
                message=field_by_name[primary].ask,
            )

        return NextAction(
            type="check",
            check=check,
            cause_id=current.id,
            fields=unknown_fields,
            message=check.instruction,
            source=check.source,
        )

    return NextAction(
        type="escalate",
        cause_id=current.id,
        message=(
            f"The documented checks for {current.name} are complete but do not resolve it."
        ),
    )


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


def _is_known(facts: dict[str, Any], field_name: str) -> bool:
    if field_name not in facts:
        return False
    return facts[field_name] != UNCLEAR


def _unique_sorted(fields: Iterable[str]) -> list[str]:
    return sorted(set(fields))


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
                or not math.isfinite(value)
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

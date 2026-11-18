"""Plain-language wording for cause statuses, reasons and outcomes.

Pure functions over a fault graph and an engine result — no I/O, no LLM. The
words come from the graph (``value_phrases``, ``unsure_phrase``); this module
only decides which facts to mention and how to join them.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.engine.engine import CauseStatus, DiagnosticState, Truth, evaluate_condition
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
    display_page,
    format_fact,
)
from app.manuals import section_short_label, short_doc_name

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


def not_checked_reason(outcome_type: str) -> str:
    """Why a cause was never checked, given how the session ended."""
    if outcome_type == "root_cause":
        return "A root cause was found first"
    if outcome_type == "escalate":
        return "The session was escalated first"
    return "The session was closed first"


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
        unsure_bits = _join_phrases([unsure_phrase(field_by_name[name]) for name in unsure])
        phrases.append(f"{unsure_bits} {UNSURE_NOTE}")
    text = _join_phrases(phrases)
    if cause.status == "contradiction":
        return f"Answers conflict: {_lower_first(text)}"
    return _upper_first(text)


def _join(field_by_name: dict[str, FieldSpec], names: list[str], facts: dict[str, Any]) -> str:
    return _join_phrases([fact_phrase(field_by_name[name], facts[name]) for name in names])


def _join_phrases(phrases: list[str]) -> str:
    """``Air flow clear; heatsink was clean`` — only the first part keeps its capital."""
    return "; ".join(
        phrase if index == 0 else _lower_first(phrase) for index, phrase in enumerate(phrases)
    )


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


# --- Outcome text ---------------------------------------------------------

ESCALATE = "Escalate to a senior technician or OEM support"

_NUMBER_WORDS = (
    "zero", "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "ten",
)


class Outcome(BaseModel):
    """How a session ended, ready to show: a headline, paragraphs, a source line."""

    model_config = ConfigDict(extra="forbid")

    # "Root cause: <cause>" or "Escalated".
    headline: str
    # The action first, then what happened to the other causes.
    paragraphs: list[str]
    # "ABB ACS580 firmware manual · A581 Fan · p. 543"; None for escalations.
    source: str | None


def build_outcome(graph: FaultGraph, state: DiagnosticState) -> Outcome | None:
    """Short readable outcome for a root cause or an escalation.

    ``None`` while the engine still has a check to ask.
    """
    action = state.next_action
    if action.type == "root_cause" and action.cause_id is not None:
        return _root_cause_outcome(graph, state, action.cause_id)
    if action.type == "escalate":
        return Outcome(
            headline="Escalated",
            paragraphs=_escalation_paragraphs(graph, state),
            source=None,
        )
    return None


def _root_cause_outcome(
    graph: FaultGraph, state: DiagnosticState, cause_id: str
) -> Outcome:
    cause = _graph_cause(graph, cause_id)
    paragraphs = [_sentence(cause.corrective_action)]
    others = [item for item in state.causes if item.cause_id != cause_id]
    if others:
        paragraphs.append(_other_causes_sentence(others))
    return Outcome(
        headline=f"Root cause: {_sentence_body(cause.name)}",
        paragraphs=paragraphs,
        source=_citation(cause.action_source),
    )


def _other_causes_sentence(others: list[CauseStatus]) -> str:
    groups = [
        (sum(1 for item in others if item.status == status), verb)
        for status, verb in (
            ("ruled_out", "ruled out"),
            ("open", "not checked"),
            ("inconclusive", "left unresolved"),
            ("confirmed", "also confirmed"),
        )
    ]
    groups = [(count, verb) for count, verb in groups if count]
    total = len(others)
    if len(groups) == 1:
        verb = groups[0][1]
        if total == 1:
            return f"The other cause was {verb}."
        return f"The other {_number(total)} causes were {verb}."
    parts = [f"{_number(count)} {_was(count)} {verb}" for count, verb in groups]
    return f"Of the other {_number(total)} causes, {_and_join(parts)}."


def _escalation_paragraphs(graph: FaultGraph, state: DiagnosticState) -> list[str]:
    field_by_name = {field.name: field for field in graph.fields}
    check_by_id = {check.id: check for check in graph.checks}
    facts = state.facts
    total = len(state.causes)

    contradictions = [item for item in state.causes if item.status == "contradiction"]
    if contradictions:
        cause = contradictions[0]
        reason = cause_reason(graph, cause, facts) or "the answers conflict"
        recheck = _rechecks(graph, cause.because, check_by_id)
        return [
            f"The answers both confirm and rule out {_lower_first(cause.name)}: "
            f"{_lower_first(reason.removeprefix('Answers conflict: '))}.",
            _escalate_sentence(recheck),
        ]

    ruled_out = [item for item in state.causes if item.status == "ruled_out"]
    inconclusive = [item for item in state.causes if item.status == "inconclusive"]
    open_causes = [item for item in state.causes if item.status == "open"]

    sentences = [
        f"None of the {_number(total)} documented causes could be confirmed."
        if total > 1
        else "The documented cause could not be confirmed."
    ]
    if ruled_out:
        if len(ruled_out) == total:
            sentences.append(
                f"All {_number(total)} were ruled out by the checks."
                if total > 1
                else "It was ruled out by the checks."
            )
        else:
            count = len(ruled_out)
            sentences.append(
                f"{_upper_first(_number(count))} {_was(count)} ruled out by the checks."
            )

    unsure_fields: list[str] = []
    for item in inconclusive:
        answered = [
            name for name in item.because if facts.get(name) not in (None, UNCLEAR)
        ]
        unsure = [name for name in item.because if facts.get(name) == UNCLEAR]
        unsure_fields.extend(name for name in unsure if name not in unsure_fields)
        known = _and_join(
            [_lower_first(fact_phrase(field_by_name[name], facts[name])) for name in answered]
        )
        not_sure = (
            "you weren't sure about "
            + _and_join([unsure_subject(field_by_name[name]) for name in unsure])
            if unsure
            else ""
        )
        if known and not_sure:
            detail = f"{known}, but {not_sure}"
        else:
            detail = known or not_sure
        sentences.append(f"{_sentence_body(item.name)} is still possible: {detail}.")

    for item in open_causes:
        sentences.append(
            f"The documented checks do not settle {_lower_first(item.name)}."
        )

    recheck = _rechecks(graph, unsure_fields, check_by_id)
    return [" ".join(sentences), _escalate_sentence(recheck)]


def _rechecks(
    graph: FaultGraph, field_names: list[str], check_by_id: dict[str, Check]
) -> list[str]:
    """What to recheck, in graph check order, for checks collecting these fields."""
    wanted = set(field_names)
    return [
        check.recheck if check.recheck is not None else _lower_first(check.instruction.rstrip("."))
        for check in graph.checks
        if wanted & set(check.collects)
    ]


def _escalate_sentence(recheck: list[str]) -> str:
    if recheck:
        return f"{ESCALATE}, and recheck {_and_join(recheck)} first."
    return f"{ESCALATE}."


def _citation(source: Source) -> str:
    page = display_page(source)
    page_bit = f" · p. {page}" if page is not None else ""
    return f"{short_doc_name(source.doc_id)} · {section_short_label(source.section)}{page_bit}"


def _number(count: int) -> str:
    return _NUMBER_WORDS[count] if count < len(_NUMBER_WORDS) else str(count)


def _was(count: int) -> str:
    return "was" if count == 1 else "were"


def _and_join(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _sentence(text: str) -> str:
    """A sentence ending in exactly one full stop (or its own ? / !)."""
    text = text.strip()
    return text if text.endswith((".", "?", "!")) else f"{text}."


def _sentence_body(text: str) -> str:
    return text.strip().rstrip(".")

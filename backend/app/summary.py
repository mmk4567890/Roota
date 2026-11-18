"""Build a session summary from the event log and diagnostic state.

Pure functions — no I/O, no LLM. The API layer loads the session and graph,
evaluates state, then calls ``build_summary``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.engine.engine import CauseStatus, DiagnosticState
from app.engine.replay import is_event_undone, session_is_closed
from app.engine.schema import (
    FaultGraph,
    FieldSpec,
    Source,
    display_page,
    field_value_label,
)
from app.manuals import full_doc_citation, section_short_label, short_doc_name
from app.models import Event
from app.wording import (
    cause_reason,
    cause_status_label,
    not_checked_reason,
    outcome_paragraphs,
)


class FactReport(BaseModel):
    """One field value as reported by the technician (or later undone)."""

    model_config = ConfigDict(extra="forbid")

    field: str
    field_label: str
    value: Any
    value_label: str
    reported_at: datetime
    event_id: int
    how: Literal["form", "observation"]
    text: str | None = None
    undone: bool = False


class SummaryCause(BaseModel):
    """A cause as the report shows it: badge text and one plain reason."""

    model_config = ConfigDict(extra="forbid")

    cause_id: str
    name: str
    status: Literal["confirmed", "ruled_out", "contradiction", "open", "inconclusive"]
    # "Not checked" for causes still open once the session has an outcome.
    status_label: str
    # None while nothing has decided the cause.
    reason: str | None


class RootCauseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause_id: str
    name: str
    corrective_action: str
    source: Source


class CitationUsed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    # Short name for compact UI lines; full title+number for expanded passages.
    short_name: str
    full_title: str
    section: str
    section_label: str
    # Printed page when the graph provides one; otherwise the PDF page.
    page: int | None
    used_for: str
    # Verbatim manual passage when the doc is ingested; None when unavailable.
    passage: str | None = None


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    fault_id: str
    display_name: str
    equipment_label: str
    status: Literal["active", "closed"]
    started_at: datetime
    closed_at: datetime | None
    causes: list[SummaryCause]
    root_cause: RootCauseSummary | None
    # Plain sentences for the root cause or escalation; None while in progress.
    outcome: list[str] | None
    facts: list[FactReport]
    citations: list[CitationUsed]


def build_summary(
    *,
    session_id: UUID,
    equipment_label: str,
    started_at: datetime,
    graph: FaultGraph,
    events: list[Event],
    state: DiagnosticState,
) -> SessionSummary:
    closed = session_is_closed(events)
    closed_at = _closed_at(events) if closed else None

    root_cause: RootCauseSummary | None = None
    if state.next_action.type == "root_cause" and state.next_action.cause_id:
        cause = next(c for c in graph.causes if c.id == state.next_action.cause_id)
        root_cause = RootCauseSummary(
            cause_id=cause.id,
            name=cause.name,
            corrective_action=cause.corrective_action,
            source=cause.action_source,
        )

    return SessionSummary(
        session_id=session_id,
        fault_id=graph.fault_id,
        display_name=graph.display_name,
        equipment_label=equipment_label,
        status="closed" if closed else "active",
        started_at=started_at,
        closed_at=closed_at,
        causes=_summary_causes(
            graph,
            state.causes,
            state.facts,
            outcome_reached=closed or state.next_action.type in ("root_cause", "escalate"),
            outcome_type=state.next_action.type,
        ),
        root_cause=root_cause,
        outcome=outcome_paragraphs(graph, state),
        facts=_fact_reports(events, graph),
        citations=_citations_used(graph, state),
    )


def render_markdown(summary: SessionSummary) -> str:
    lines: list[str] = [
        f"# {summary.display_name}",
        "",
        "Session report",
        "",
        f"- **Session:** `{summary.session_id}`",
        f"- **Equipment:** {summary.equipment_label}",
        f"- **Fault:** `{summary.fault_id}`",
        f"- **Status:** {summary.status}",
        f"- **Started:** {summary.started_at.isoformat()}",
    ]
    if summary.closed_at is not None:
        lines.append(f"- **Closed:** {summary.closed_at.isoformat()}")
    lines.append("")

    heading = (
        "Root cause"
        if summary.root_cause is not None
        else "Escalation"
        if summary.outcome is not None
        else "Outcome"
    )
    lines.extend([f"## {heading}", ""])
    if summary.outcome is not None:
        for paragraph in summary.outcome:
            lines.extend([paragraph, ""])
    elif summary.status == "closed":
        lines.extend(["Session closed without a diagnosis.", ""])
    else:
        lines.extend(["Session still in progress.", ""])

    lines.extend(["## Cause checklist", ""])
    for cause in summary.causes:
        reason = f" — {cause.reason}" if cause.reason else ""
        lines.append(f"- **{cause.status_label}** · {cause.name}{reason}")
    lines.append("")

    lines.extend(["## Facts reported", ""])
    if not summary.facts:
        lines.append("_No facts reported._")
    else:
        for fact in summary.facts:
            undone = " _(undone)_" if fact.undone else ""
            how = "typed observation" if fact.how == "observation" else "form"
            text_bit = f' — "{fact.text}"' if fact.text else ""
            lines.append(
                f"- {fact.field_label}: {fact.value_label} via {how} at "
                f"{fact.reported_at.isoformat()}{text_bit}{undone}"
            )
    lines.append("")

    lines.extend(["## Manual citations", ""])
    if not summary.citations:
        lines.append("_No citations used yet._")
    else:
        for cite in summary.citations:
            page = f", p. {cite.page}" if cite.page is not None else ""
            lines.append(
                f"- {cite.short_name} · {cite.section_label}{page} — {cite.used_for}"
            )
            if cite.passage:
                lines.append("")
                lines.append(f"  _{cite.full_title}_")
                lines.append("")
                lines.append(f"  > {cite.passage}")
                lines.append("")
    lines.append("")
    return "\n".join(lines)


def _field_spec(graph: FaultGraph, field_name: str) -> FieldSpec | None:
    return next((field for field in graph.fields if field.name == field_name), None)


def _summary_causes(
    graph: FaultGraph,
    causes: list[CauseStatus],
    facts: dict[str, Any],
    *,
    outcome_reached: bool,
    outcome_type: str,
) -> list[SummaryCause]:
    summary_causes: list[SummaryCause] = []
    for cause in causes:
        not_checked = outcome_reached and cause.status == "open"
        summary_causes.append(
            SummaryCause(
                cause_id=cause.cause_id,
                name=cause.name,
                status=cause.status,
                status_label=cause_status_label(
                    cause.status, outcome_reached=outcome_reached
                ),
                reason=(
                    not_checked_reason(outcome_type)
                    if not_checked
                    else cause_reason(graph, cause, facts)
                ),
            )
        )
    return summary_causes


def _fact_report(
    *,
    graph: FaultGraph,
    field: str,
    value: Any,
    reported_at: datetime,
    event_id: int,
    how: Literal["form", "observation"],
    text: str | None,
    undone: bool,
) -> FactReport:
    spec = _field_spec(graph, field)
    if spec is None:
        field_label = field
        value_label = str(value)
    else:
        field_label = spec.label
        value_label = field_value_label(spec, value)
    return FactReport(
        field=field,
        field_label=field_label,
        value=value,
        value_label=value_label,
        reported_at=reported_at,
        event_id=event_id,
        how=how,
        text=text,
        undone=undone,
    )


def _fact_reports(events: list[Event], graph: FaultGraph) -> list[FactReport]:
    reports: list[FactReport] = []
    for event in events:
        if event.type == "facts_reported":
            facts = dict(event.payload.get("facts") or {})
            for field, value in facts.items():
                reports.append(
                    _fact_report(
                        graph=graph,
                        field=str(field),
                        value=value,
                        reported_at=event.created_at,
                        event_id=event.id,
                        how="form",
                        text=None,
                        undone=is_event_undone(events, event.id),
                    )
                )
        elif event.type == "observation":
            text = event.payload.get("text")
            text_str = str(text) if text is not None else None
            extracted = dict(event.payload.get("extracted") or {})
            for field, value in extracted.items():
                reports.append(
                    _fact_report(
                        graph=graph,
                        field=str(field),
                        value=value,
                        reported_at=event.created_at,
                        event_id=event.id,
                        how="observation",
                        text=text_str,
                        undone=is_event_undone(events, event.id),
                    )
                )
            for field in event.payload.get("unclear_fields") or []:
                reports.append(
                    _fact_report(
                        graph=graph,
                        field=str(field),
                        value="unclear",
                        reported_at=event.created_at,
                        event_id=event.id,
                        how="observation",
                        text=text_str,
                        undone=is_event_undone(events, event.id),
                    )
                )
    return reports


def _citations_used(graph: FaultGraph, state: DiagnosticState) -> list[CitationUsed]:
    check_by_id = {check.id: check for check in graph.checks}
    citations: list[CitationUsed] = []
    # One entry per passage: the same document + page + section cited by
    # several checks is listed once, at its first use.
    seen: set[tuple[str, int | None, str]] = set()

    def add(source: Source, used_for: str) -> None:
        page = display_page(source)
        key = (source.doc_id, page, source.section)
        if key in seen:
            return
        seen.add(key)
        citations.append(
            CitationUsed(
                doc_id=source.doc_id,
                short_name=short_doc_name(source.doc_id),
                full_title=full_doc_citation(source.doc_id),
                section=source.section,
                section_label=section_short_label(source.section),
                page=page,
                used_for=used_for,
            )
        )

    for check_id in state.checks_completed:
        check = check_by_id[check_id]
        add(check.source, f"check:{check.id}")

    action = state.next_action
    if action.type == "check" and action.check is not None:
        add(action.check.source, f"check:{action.check.id}")
    if action.type == "root_cause" and action.source is not None and action.cause_id:
        add(action.source, f"cause:{action.cause_id}")

    return citations


def _closed_at(events: list[Event]) -> datetime | None:
    for event in reversed(events):
        if event.type == "closed" and not is_event_undone(events, event.id):
            return event.created_at
    return None


def with_citation_passages(
    summary: SessionSummary,
    passages: dict[tuple[str, int | None], str],
) -> SessionSummary:
    """Attach verbatim passages keyed by (doc_id, page). Missing keys stay None."""
    enriched = [
        cite.model_copy(update={"passage": passages.get((cite.doc_id, cite.page))})
        for cite in summary.citations
    ]
    return summary.model_copy(update={"citations": enriched})

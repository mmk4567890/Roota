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
from app.engine.schema import FaultGraph, Source
from app.models import Event


class FactReport(BaseModel):
    """One field value as reported by the technician (or later undone)."""

    model_config = ConfigDict(extra="forbid")

    field: str
    value: Any
    reported_at: datetime
    event_id: int
    how: Literal["form", "observation"]
    text: str | None = None
    undone: bool = False


class RootCauseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause_id: str
    name: str
    corrective_action: str
    source: Source


class CitationUsed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    section: str
    page: int | None
    used_for: str


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    fault_id: str
    display_name: str
    equipment_label: str
    status: Literal["active", "closed"]
    started_at: datetime
    closed_at: datetime | None
    causes: list[CauseStatus]
    root_cause: RootCauseSummary | None
    escalation_reason: str | None
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
    escalation_reason: str | None = None
    if state.next_action.type == "root_cause" and state.next_action.cause_id:
        cause = next(c for c in graph.causes if c.id == state.next_action.cause_id)
        root_cause = RootCauseSummary(
            cause_id=cause.id,
            name=cause.name,
            corrective_action=cause.corrective_action,
            source=cause.action_source,
        )
    elif state.next_action.type == "escalate":
        escalation_reason = state.next_action.message

    return SessionSummary(
        session_id=session_id,
        fault_id=graph.fault_id,
        display_name=graph.display_name,
        equipment_label=equipment_label,
        status="closed" if closed else "active",
        started_at=started_at,
        closed_at=closed_at,
        causes=list(state.causes),
        root_cause=root_cause,
        escalation_reason=escalation_reason,
        facts=_fact_reports(events),
        citations=_citations_used(graph, state),
    )


def render_markdown(summary: SessionSummary) -> str:
    lines: list[str] = [
        f"# Session summary — {summary.display_name}",
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

    if summary.root_cause is not None:
        rc = summary.root_cause
        lines.extend(
            [
                "## Root cause",
                "",
                f"**{rc.name}** (`{rc.cause_id}`)",
                "",
                rc.corrective_action,
                "",
                _format_source(rc.source),
                "",
            ]
        )
    elif summary.escalation_reason is not None:
        lines.extend(
            [
                "## Escalation",
                "",
                summary.escalation_reason,
                "",
            ]
        )
    else:
        lines.extend(["## Outcome", "", "Session still in progress.", ""])

    lines.extend(["## Cause statuses", ""])
    for cause in summary.causes:
        because = f" — {', '.join(cause.because)}" if cause.because else ""
        lines.append(f"- **{cause.name}** (`{cause.cause_id}`): {cause.status}{because}")
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
                f"- `{fact.field}` = {fact.value!r} via {how} at "
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
                f"- `{cite.doc_id}` §{cite.section}{page} — {cite.used_for}"
            )
    lines.append("")
    return "\n".join(lines)


def _fact_reports(events: list[Event]) -> list[FactReport]:
    reports: list[FactReport] = []
    for event in events:
        if event.type == "facts_reported":
            facts = dict(event.payload.get("facts") or {})
            for field, value in facts.items():
                reports.append(
                    FactReport(
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
                    FactReport(
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
                    FactReport(
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
    seen: set[tuple[str, str, int | None, str]] = set()

    def add(source: Source, used_for: str) -> None:
        key = (source.doc_id, source.section, source.page, used_for)
        if key in seen:
            return
        seen.add(key)
        citations.append(
            CitationUsed(
                doc_id=source.doc_id,
                section=source.section,
                page=source.page,
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


def _format_source(source: Source) -> str:
    page = f", p. {source.page}" if source.page is not None else ""
    return f"Source: `{source.doc_id}` §{source.section}{page}"

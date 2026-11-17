from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.engine.engine import DiagnosticState, evaluate, validate_facts
from app.engine.replay import is_event_undone, replay_facts, session_is_closed
from app.engine.schema import FaultGraph
from app.graphs.loader import get_graphs
from app.models import (
    Event,
    FactsReport,
    ObservationReport,
    ObservationResponse,
    SessionCreate,
    SessionView,
    UndoRequest,
)
from app.summary import (
    SessionSummary,
    build_summary,
    render_markdown,
    with_citation_passages,
)
from app.parser.base import ObservationParser, ParseError, ParseResult
from app.parser.validate import validate_parse
from app.repository import (
    EventAlreadyUndoneError,
    SessionClosedError,
    SessionRecord,
    SessionRepository,
)
from app.retrieval.evidence import get_evidence
from app.retrieval.store import TBD_MANUAL, ManualStore
from app.routers.docs import get_manual_store

logger = logging.getLogger(__name__)


router = APIRouter(tags=["sessions"])


def get_repository() -> SessionRepository:
    """Overridden in main with the shared SQLite repository."""
    raise RuntimeError("Repository dependency was not configured")


def get_parser(request: Request) -> ObservationParser:
    """The parser main's lifespan built from ROOTA_PARSER."""
    parser = getattr(request.app.state, "parser", None)
    if parser is None:
        raise RuntimeError("Observation parser was not configured")
    return parser


@router.post(
    "/sessions",
    response_model=SessionView,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    payload: SessionCreate,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
    store: ManualStore = Depends(get_manual_store),
) -> SessionView:
    graph = _require_graph(payload.fault_id, graphs)
    if payload.initial_facts:
        _validate_facts_or_422(graph, payload.initial_facts)

    record = repository.create_session(payload.fault_id, payload.equipment_label)
    if payload.initial_facts:
        repository.append_event(
            record.id,
            "facts_reported",
            {"facts": payload.initial_facts, "check_id": None},
        )
    return _session_view(record, repository, graph, store)


@router.get("/sessions/{session_id}", response_model=SessionView)
def get_session(
    session_id: UUID,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
    store: ManualStore = Depends(get_manual_store),
) -> SessionView:
    record = _require_session(session_id, repository)
    graph = _graph_for_session(record, graphs)
    return _session_view(record, repository, graph, store)


@router.post("/sessions/{session_id}/facts", response_model=SessionView)
def report_facts(
    session_id: UUID,
    payload: FactsReport,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
    store: ManualStore = Depends(get_manual_store),
) -> SessionView:
    record = _require_session(session_id, repository)
    graph = _graph_for_session(record, graphs)
    events = repository.list_events(session_id)
    _reject_if_closed(events)

    if not payload.facts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="facts must not be empty",
        )

    _validate_facts_or_422(graph, payload.facts)
    _validate_check_id(graph, payload.check_id, payload.facts)

    _append_or_409(
        repository,
        session_id,
        "facts_reported",
        {"facts": payload.facts, "check_id": payload.check_id},
    )
    return _session_view(record, repository, graph, store)


@router.post(
    "/sessions/{session_id}/observations",
    response_model=ObservationResponse,
)
def report_observation(
    session_id: UUID,
    payload: ObservationReport,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
    parser: ObservationParser = Depends(get_parser),
    store: ManualStore = Depends(get_manual_store),
) -> ObservationResponse:
    record = _require_session(session_id, repository)
    graph = _graph_for_session(record, graphs)
    events = repository.list_events(session_id)
    _reject_if_closed(events)

    if payload.check_id is not None:
        check = next((item for item in graph.checks if item.id == payload.check_id), None)
        if check is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unknown check_id '{payload.check_id}'",
            )
        expected_fields = list(check.collects)
    else:
        expected_fields = _expected_fields_from_state(graph, events)

    try:
        raw = parser.parse(payload.text, graph, expected_fields)
        parsed = validate_parse(raw, graph)
    except ParseError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    _append_or_409(
        repository,
        session_id,
        "observation",
        {
            "text": payload.text,
            "check_id": payload.check_id,
            "extracted": parsed.extracted,
            "unclear_fields": parsed.unclear_fields,
            "rejected": [item.model_dump() for item in parsed.rejected],
        },
    )

    view = _session_view(record, repository, graph, store)
    return ObservationResponse(
        id=view.id,
        fault_id=view.fault_id,
        equipment_label=view.equipment_label,
        status=view.status,
        created_at=view.created_at,
        events=view.events,
        state=view.state,
        parse=parsed,
        message=_observation_message(parsed),
    )


@router.post("/sessions/{session_id}/undo", response_model=SessionView)
def undo_event(
    session_id: UUID,
    payload: UndoRequest,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
    store: ManualStore = Depends(get_manual_store),
) -> SessionView:
    record = _require_session(session_id, repository)
    graph = _graph_for_session(record, graphs)
    events = repository.list_events(session_id)
    _reject_if_closed(events)

    target = next((event for event in events if event.id == payload.event_id), None)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {payload.event_id} not found in session {session_id}",
        )
    if target.type == "undo":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="undo events cannot be undone",
        )
    if is_event_undone(events, target.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Event {target.id} is already undone",
        )

    _append_or_409(repository, session_id, "undo", {"target_event_id": target.id})
    return _session_view(record, repository, graph, store)


@router.post("/sessions/{session_id}/close", response_model=SessionView)
def close_session(
    session_id: UUID,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
    store: ManualStore = Depends(get_manual_store),
) -> SessionView:
    record = _require_session(session_id, repository)
    graph = _graph_for_session(record, graphs)
    events = repository.list_events(session_id)
    _reject_if_closed(events)

    _append_or_409(repository, session_id, "closed", {})
    return _session_view(record, repository, graph, store)


@router.get(
    "/sessions/{session_id}/summary",
    response_model=None,
    responses={
        200: {
            "content": {
                "application/json": {"schema": SessionSummary.model_json_schema()},
                "text/markdown": {"schema": {"type": "string"}},
            }
        }
    },
)
def get_session_summary(
    session_id: UUID,
    format: str | None = Query(default=None, pattern="^(json|markdown)$"),
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
    store: ManualStore = Depends(get_manual_store),
) -> SessionSummary | PlainTextResponse:
    """Structured session record built only from the event log and engine."""
    record = _require_session(session_id, repository)
    graph = _graph_for_session(record, graphs)
    events = repository.list_events(session_id)
    facts = replay_facts(events)
    try:
        state = evaluate(graph, facts)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Stored session facts are incompatible with the current fault graph: "
                f"{error}"
            ),
        ) from error

    summary = build_summary(
        session_id=record.id,
        equipment_label=record.equipment_label,
        started_at=record.created_at,
        graph=graph,
        events=events,
        state=state,
    )
    summary = with_citation_passages(
        summary, _citation_passages(summary, graph, store)
    )
    if format == "markdown":
        return PlainTextResponse(
            render_markdown(summary),
            media_type="text/markdown; charset=utf-8",
        )
    return summary


def _session_view(
    record: SessionRecord,
    repository: SessionRepository,
    graph: FaultGraph,
    store: ManualStore,
) -> SessionView:
    events = repository.list_events(record.id)
    facts = replay_facts(events)
    try:
        state = evaluate(graph, facts)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Stored session facts are incompatible with the current fault graph: "
                f"{error}"
            ),
        ) from error

    state = _attach_evidence(state, store)

    return SessionView(
        id=record.id,
        fault_id=record.fault_id,
        equipment_label=record.equipment_label,
        status="closed" if session_is_closed(events) else "active",
        created_at=record.created_at,
        events=events,
        state=state,
    )


def _attach_evidence(state: DiagnosticState, store: ManualStore) -> DiagnosticState:
    """API-layer only: attach verbatim manual passages to check / root_cause actions.

    Retrieval failures never fail the session: diagnostic state is independent of
    evidence. Status distinguishes no manual / nothing found / retrieval broken.
    """
    action = state.next_action
    if action.type not in ("check", "root_cause") or action.source is None:
        return state.model_copy(
            update={
                "next_action": action.model_copy(
                    update={
                        "evidence": None,
                        "evidence_status": None,
                        "evidence_error": None,
                    }
                ),
            }
        )

    if action.type == "check" and action.check is not None:
        query = action.check.instruction
    else:
        query = action.message

    source = action.source
    if source.doc_id == TBD_MANUAL:
        return state.model_copy(
            update={
                "next_action": action.model_copy(
                    update={
                        "evidence": [],
                        "evidence_status": "no_manual",
                        "evidence_error": None,
                    }
                ),
            }
        )

    try:
        if not store.has_doc(source.doc_id):
            return state.model_copy(
                update={
                    "next_action": action.model_copy(
                        update={
                            "evidence": [],
                            "evidence_status": "no_manual",
                            "evidence_error": None,
                        }
                    ),
                }
            )
        evidence = get_evidence(source, query, store=store)
    except Exception as error:
        logger.exception("Manual evidence retrieval failed")
        return state.model_copy(
            update={
                "next_action": action.model_copy(
                    update={
                        "evidence": None,
                        "evidence_status": "unavailable",
                        "evidence_error": _safe_evidence_error(error),
                    }
                ),
            }
        )

    return state.model_copy(
        update={
            "next_action": action.model_copy(
                update={
                    "evidence": evidence,
                    "evidence_status": "attached",
                    "evidence_error": None,
                }
            ),
        }
    )


def _safe_evidence_error(error: BaseException) -> str:
    """Short status for the UI: type name + fixed phrase, never paths or secrets."""
    name = type(error).__name__
    lowered = name.lower()
    # Match embedding-related exception *types* only — never str(error) (paths/keys).
    if any(token in lowered for token in ("onnx", "embedding", "tokenizer")):
        return f"{name}: embedding model not available"
    return f"{name}: retrieval failed"


def _citation_passages(
    summary: SessionSummary,
    graph: FaultGraph,
    store: ManualStore,
) -> dict[tuple[str, int | None], str]:
    """Best-effort verbatim passage per (doc_id, page) for summary citations."""
    check_by_id = {check.id: check for check in graph.checks}
    cause_by_id = {cause.id: cause for cause in graph.causes}
    passages: dict[tuple[str, int | None], str] = {}

    for cite in summary.citations:
        key = (cite.doc_id, cite.page)
        if key in passages:
            continue

        query = graph.description
        source = None
        if cite.used_for.startswith("check:"):
            check = check_by_id.get(cite.used_for.removeprefix("check:"))
            if check is not None:
                query = check.instruction
                source = check.source
        elif cite.used_for.startswith("cause:"):
            cause = cause_by_id.get(cite.used_for.removeprefix("cause:"))
            if cause is not None:
                query = cause.corrective_action
                source = cause.action_source
        if source is None:
            continue

        try:
            evidence = get_evidence(source, query, store=store)
        except Exception:
            logger.exception("Summary citation passage retrieval failed")
            continue
        cited = next((item for item in evidence if item.kind == "cited"), None)
        if cited is not None and cited.text.strip():
            passages[key] = cited.text
    return passages


def _require_session(
    session_id: UUID, repository: SessionRepository
) -> SessionRecord:
    record = repository.get_session(session_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return record


def _require_graph(fault_id: str, graphs: dict[str, FaultGraph]) -> FaultGraph:
    graph = graphs.get(fault_id)
    if graph is None:
        valid = ", ".join(sorted(graphs)) or "(none loaded)"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown fault_id '{fault_id}'. Valid ids: {valid}",
        )
    return graph


def _graph_for_session(record: SessionRecord, graphs: dict[str, FaultGraph]) -> FaultGraph:
    graph = graphs.get(record.fault_id)
    if graph is None:
        # The request is valid; the stored session refers to a graph that is no longer loaded.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session fault '{record.fault_id}' is not among the loaded fault graphs",
        )
    return graph


def _append_or_409(
    repository: SessionRepository,
    session_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    try:
        repository.append_event(session_id, event_type, payload)
    except (SessionClosedError, EventAlreadyUndoneError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


def _validate_facts_or_422(graph: FaultGraph, facts: dict[str, Any]) -> None:
    try:
        validate_facts(graph, facts)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


def _validate_check_id(
    graph: FaultGraph,
    check_id: str | None,
    facts: dict[str, Any],
) -> None:
    if check_id is None:
        return
    check = next((item for item in graph.checks if item.id == check_id), None)
    if check is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown check_id '{check_id}'",
        )
    if not any(field_name in facts for field_name in check.collects):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"check_id '{check_id}' does not collect any of the submitted fields"
            ),
        )


def _reject_if_closed(events: list[Event]) -> None:
    if session_is_closed(events):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is closed",
        )


def _expected_fields_from_state(
    graph: FaultGraph, events: list[Event]
) -> list[str]:
    try:
        state = evaluate(graph, replay_facts(events))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Stored session facts are incompatible with the current fault graph: "
                f"{error}"
            ),
        ) from error
    if state.next_action.type == "check" and state.next_action.check is not None:
        return list(state.next_action.check.collects)
    if state.next_action.fields:
        return list(state.next_action.fields)
    return []


UNCLEAR_MOVED_ON_MESSAGE = "Marked as not sure. Moving to the next check."


def _observation_message(parsed: ParseResult) -> str | None:
    if parsed.rejected:
        parts = [
            f"{item.field} ({item.reason})" for item in parsed.rejected
        ]
        return (
            "Some values could not be used — please re-phrase: "
            + "; ".join(parts)
        )
    if not parsed.extracted and not parsed.unclear_fields:
        return (
            "I didn't understand any diagnostic field values in that observation. "
            "Please re-phrase using clearer measurements or statuses."
        )
    # Unclear answers mark causes inconclusive and continue — tell the tech.
    if parsed.unclear_fields:
        return UNCLEAR_MOVED_ON_MESSAGE
    # Parser notes explain ambiguous values (e.g. ambient between derating limits).
    notes = parsed.notes.strip()
    if notes:
        return notes
    return None

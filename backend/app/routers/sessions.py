from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.engine.engine import evaluate, validate_facts
from app.engine.replay import is_event_undone, replay_facts, session_is_closed
from app.engine.schema import FaultGraph
from app.graphs.loader import get_graphs
from app.models import (
    Event,
    FactsReport,
    SessionCreate,
    SessionView,
    UndoRequest,
)
from app.repository import (
    EventAlreadyUndoneError,
    SessionClosedError,
    SessionRecord,
    SessionRepository,
)

router = APIRouter(tags=["sessions"])


def get_repository() -> SessionRepository:
    """Overridden in main with the shared SQLite repository."""
    raise RuntimeError("Repository dependency was not configured")


@router.post(
    "/sessions",
    response_model=SessionView,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    payload: SessionCreate,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
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
    return _session_view(record, repository, graph)


@router.get("/sessions/{session_id}", response_model=SessionView)
def get_session(
    session_id: UUID,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
) -> SessionView:
    record = _require_session(session_id, repository)
    graph = _graph_for_session(record, graphs)
    return _session_view(record, repository, graph)


@router.post("/sessions/{session_id}/facts", response_model=SessionView)
def report_facts(
    session_id: UUID,
    payload: FactsReport,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
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
    return _session_view(record, repository, graph)


@router.post("/sessions/{session_id}/undo", response_model=SessionView)
def undo_event(
    session_id: UUID,
    payload: UndoRequest,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
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
    return _session_view(record, repository, graph)


@router.post("/sessions/{session_id}/close", response_model=SessionView)
def close_session(
    session_id: UUID,
    repository: SessionRepository = Depends(get_repository),
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
) -> SessionView:
    record = _require_session(session_id, repository)
    graph = _graph_for_session(record, graphs)
    events = repository.list_events(session_id)
    _reject_if_closed(events)

    _append_or_409(repository, session_id, "closed", {})
    return _session_view(record, repository, graph)


def _session_view(
    record: SessionRecord,
    repository: SessionRepository,
    graph: FaultGraph,
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

    return SessionView(
        id=record.id,
        fault_id=record.fault_id,
        equipment_label=record.equipment_label,
        status="closed" if session_is_closed(events) else "active",
        created_at=record.created_at,
        events=events,
        state=state,
    )


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

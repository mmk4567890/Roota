from __future__ import annotations

from typing import Any

from app.engine.schema import UNCLEAR
from app.models import Event


def replay_facts(events: list[Event]) -> dict[str, Any]:
    """Derive current facts by replaying an append-only event log.

    Undo events mark their target event ids as skipped. Later fact-bearing
    events overwrite earlier values for the same field.
    """
    undone_ids = {
        int(event.payload["target_event_id"])
        for event in events
        if event.type == "undo"
    }

    facts: dict[str, Any] = {}
    for event in events:
        if event.id in undone_ids:
            continue
        if event.type == "facts_reported":
            facts.update(dict(event.payload["facts"]))
        elif event.type == "observation":
            facts.update(dict(event.payload.get("extracted") or {}))
            for field_name in event.payload.get("unclear_fields") or []:
                facts[str(field_name)] = UNCLEAR
    return facts


def session_is_closed(events: list[Event]) -> bool:
    """Return True when a non-undone closed event exists."""
    undone_ids = {
        int(event.payload["target_event_id"])
        for event in events
        if event.type == "undo"
    }
    return any(
        event.type == "closed" and event.id not in undone_ids for event in events
    )


def is_event_undone(events: list[Event], event_id: int) -> bool:
    return any(
        event.type == "undo" and int(event.payload["target_event_id"]) == event_id
        for event in events
    )

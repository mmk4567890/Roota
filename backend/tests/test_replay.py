from datetime import datetime, timezone
from uuid import uuid4

from app.engine.replay import is_event_undone, replay_facts, session_is_closed
from app.engine.schema import UNCLEAR
from app.models import Event


def _event(
    event_id: int,
    seq: int,
    event_type: str,
    payload: dict,
) -> Event:
    return Event(
        id=event_id,
        session_id=uuid4(),
        seq=seq,
        type=event_type,  # type: ignore[arg-type]
        payload=payload,
        created_at=datetime.now(timezone.utc),
    )


def test_replay_applies_facts_in_order() -> None:
    events = [
        _event(1, 1, "facts_reported", {"facts": {"fan_status": "noisy"}, "check_id": None}),
        _event(2, 2, "facts_reported", {"facts": {"fan_status": "normal"}, "check_id": None}),
        _event(3, 3, "facts_reported", {"facts": {"load_percent": 95}, "check_id": None}),
    ]

    assert replay_facts(events) == {
        "fan_status": "normal",
        "load_percent": 95,
    }


def test_replay_skips_undone_events() -> None:
    events = [
        _event(1, 1, "facts_reported", {"facts": {"fan_status": "normal"}, "check_id": None}),
        _event(2, 2, "facts_reported", {"facts": {"load_percent": 95}, "check_id": None}),
        _event(3, 3, "undo", {"target_event_id": 2}),
    ]

    assert replay_facts(events) == {"fan_status": "normal"}
    assert is_event_undone(events, 2) is True
    assert is_event_undone(events, 1) is False


def test_replay_observation_extracted_and_unclear_fields() -> None:
    events = [
        _event(
            1,
            1,
            "observation",
            {
                "text": "fan looks fine, load unclear",
                "check_id": "check_fan_operation",
                "extracted": {"fan_status": "normal"},
                "unclear_fields": ["load_percent"],
            },
        )
    ]

    assert replay_facts(events) == {
        "fan_status": "normal",
        "load_percent": UNCLEAR,
    }


def test_session_is_closed_respects_undo() -> None:
    events = [
        _event(1, 1, "closed", {}),
    ]
    assert session_is_closed(events) is True

    reopened = [
        _event(1, 1, "closed", {}),
        _event(2, 2, "undo", {"target_event_id": 1}),
    ]
    assert session_is_closed(reopened) is False

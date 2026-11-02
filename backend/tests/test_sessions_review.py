from __future__ import annotations

import gc
import warnings
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.graphs.loader import get_graphs
from app.main import app
from app.repository import (
    EventAlreadyUndoneError,
    SessionClosedError,
    SQLiteSessionRepository,
)


def _start(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/sessions",
        json={"fault_id": "overtemperature", "equipment_label": "Line 3 drive"},
    )
    assert response.status_code == 201
    return response.json()


def test_repository_closes_every_connection(tmp_path: Path) -> None:
    # sqlite3's context manager commits but never closes; leaked connections
    # surface as ResourceWarning "unclosed database" when collected.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        repo = SQLiteSessionRepository(tmp_path / "leak.db")
        session = repo.create_session("overtemperature", "drive")
        for _ in range(3):
            repo.append_event(session.id, "facts_reported", {"facts": {}, "check_id": None})
        repo.get_session(session.id)
        repo.list_events(session.id)
        del repo
        gc.collect()

    leaks = [w for w in caught if "unclosed database" in str(w.message)]
    assert leaks == []


def test_append_to_missing_session_raises_key_error(tmp_path: Path) -> None:
    # Previously ROLLBACK ran twice and an OperationalError masked the KeyError.
    from uuid import uuid4

    repo = SQLiteSessionRepository(tmp_path / "missing.db")
    with pytest.raises(KeyError, match="not found"):
        repo.append_event(uuid4(), "closed", {})


def test_repository_rejects_append_after_close(tmp_path: Path) -> None:
    repo = SQLiteSessionRepository(tmp_path / "closed.db")
    session = repo.create_session("overtemperature", "drive")
    repo.append_event(session.id, "closed", {})

    with pytest.raises(SessionClosedError):
        repo.append_event(session.id, "facts_reported", {"facts": {}, "check_id": None})
    assert len(repo.list_events(session.id)) == 1


def test_repository_rejects_second_undo_of_same_event(tmp_path: Path) -> None:
    # The route checks this too, but only the transaction makes it race-free.
    repo = SQLiteSessionRepository(tmp_path / "undo.db")
    session = repo.create_session("overtemperature", "drive")
    target = repo.append_event(
        session.id, "facts_reported", {"facts": {"fan_status": "normal"}, "check_id": None}
    )
    repo.append_event(session.id, "undo", {"target_event_id": target.id})

    with pytest.raises(EventAlreadyUndoneError):
        repo.append_event(session.id, "undo", {"target_event_id": target.id})


def test_stored_session_with_unloaded_graph_is_conflict_not_validation_error(
    client: TestClient,
) -> None:
    session = _start(client)
    app.dependency_overrides[get_graphs] = lambda: {}
    try:
        response = client.get(f"/sessions/{session['id']}")
    finally:
        app.dependency_overrides.pop(get_graphs, None)

    assert response.status_code == 409
    assert "overtemperature" in response.json()["detail"]


def test_new_session_with_unknown_fault_is_still_422(client: TestClient) -> None:
    response = client.post(
        "/sessions", json={"fault_id": "no_such_fault", "equipment_label": "drive"}
    )
    assert response.status_code == 422
    assert "overtemperature" in response.json()["detail"]


def test_proposal_demo_through_the_api(client: TestClient) -> None:
    session = _start(client)
    url = f"/sessions/{session['id']}/facts"
    assert session["state"]["next_action"]["check"]["id"] == "check_fan_operation"

    steps = [
        ({"fan_status": "normal"}, "check_airflow_path"),
        ({"airflow_obstruction": "none", "heatsink_condition": "clean"}, "check_load_level"),
        ({"load_percent": 95}, "check_load_duty_cycle"),
    ]
    for facts, expected_check in steps:
        response = client.post(url, json={"facts": facts})
        assert response.status_code == 200
        assert response.json()["state"]["next_action"]["check"]["id"] == expected_check

    final = client.get(f"/sessions/{session['id']}").json()
    ruled_out = sorted(c["cause_id"] for c in final["state"]["causes"] if c["status"] == "ruled_out")
    assert ruled_out == ["blocked_airflow", "cooling_fan_failure"]
    assert [event["seq"] for event in final["events"]] == [1, 2, 3]

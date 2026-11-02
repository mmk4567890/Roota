from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.engine.schema import FaultGraph
from app.graphs import loader
from app.main import app


def _create_session(
    client: TestClient,
    *,
    fault_id: str = "overtemperature",
    equipment_label: str = "Line 3 conveyor drive",
    initial_facts: dict | None = None,
) -> dict:
    body: dict = {
        "fault_id": fault_id,
        "equipment_label": equipment_label,
    }
    if initial_facts is not None:
        body["initial_facts"] = initial_facts
    response = client.post("/sessions", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_session_valid(client: TestClient) -> None:
    body = _create_session(client)

    assert body["fault_id"] == "overtemperature"
    assert body["equipment_label"] == "Line 3 conveyor drive"
    assert body["status"] == "active"
    assert body["events"] == []
    assert body["state"]["next_action"]["type"] == "check"
    assert body["state"]["next_action"]["check"]["id"] == "check_fan_operation"


def test_create_session_unknown_fault_id_returns_422(client: TestClient) -> None:
    response = client.post(
        "/sessions",
        json={
            "fault_id": "not_a_real_fault",
            "equipment_label": "Bay 2",
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "not_a_real_fault" in detail
    assert "overtemperature" in detail


def test_create_session_rejects_unknown_body_key(client: TestClient) -> None:
    response = client.post(
        "/sessions",
        json={
            "fault_id": "overtemperature",
            "equipment_label": "Bay 2",
            "extra_field": True,
        },
    )
    assert response.status_code == 422


def test_scenario_1_to_2_to_3_via_api(client: TestClient) -> None:
    created = _create_session(client)
    session_id = created["id"]
    assert created["state"]["next_action"]["check"]["id"] == "check_fan_operation"

    step2 = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "normal"}, "check_id": "check_fan_operation"},
    )
    assert step2.status_code == 200, step2.text
    body2 = step2.json()
    assert body2["state"]["causes"]
    fan_status = next(
        cause for cause in body2["state"]["causes"] if cause["cause_id"] == "cooling_fan_failure"
    )
    assert fan_status["status"] == "ruled_out"
    assert body2["state"]["next_action"]["type"] == "check"
    assert body2["state"]["next_action"]["check"]["id"] == "check_airflow_path"

    step3 = client.post(
        f"/sessions/{session_id}/facts",
        json={
            "facts": {
                "airflow_obstruction": "none",
                "heatsink_condition": "clean",
                "load_percent": 95,
            }
        },
    )
    assert step3.status_code == 200, step3.text
    body3 = step3.json()
    load_status = next(
        cause for cause in body3["state"]["causes"] if cause["cause_id"] == "excessive_load"
    )
    assert load_status["status"] == "open"
    assert body3["state"]["next_action"]["type"] == "check"
    assert body3["state"]["next_action"]["check"]["id"] == "check_load_duty_cycle"
    assert body3["state"]["next_action"]["cause_id"] == "excessive_load"


def test_facts_empty_dict_returns_422(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    response = client.post(f"/sessions/{session_id}/facts", json={"facts": {}})
    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


def test_facts_unknown_field_returns_422(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    response = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"not_a_field": 1}},
    )
    assert response.status_code == 422
    assert "not_a_field" in response.json()["detail"]


def test_facts_invalid_enum_returns_422(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    response = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "spinning_fast"}},
    )
    assert response.status_code == 422
    assert "fan_status" in response.json()["detail"]


def test_facts_invalid_number_returns_422(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    response = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"load_percent": "ninety"}},
    )
    assert response.status_code == 422
    assert "load_percent" in response.json()["detail"]


def test_facts_unclear_allowed(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    response = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "unclear"}, "check_id": "check_fan_operation"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"]["next_action"]["type"] == "need_info"


def test_facts_unknown_check_id_returns_422(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    response = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "normal"}, "check_id": "missing_check"},
    )
    assert response.status_code == 422
    assert "missing_check" in response.json()["detail"]


def test_facts_check_id_must_collect_submitted_field(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    response = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "normal"}, "check_id": "check_load_level"},
    )
    assert response.status_code == 422
    assert "does not collect" in response.json()["detail"]


def test_facts_rejects_unknown_body_key(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    response = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "normal"}, "unexpected": 1},
    )
    assert response.status_code == 422


def test_get_nonexistent_session_returns_404(client: TestClient) -> None:
    response = client.get(f"/sessions/{uuid4()}")
    assert response.status_code == 404


def test_undo_restores_previous_next_action(client: TestClient) -> None:
    created = _create_session(client)
    session_id = created["id"]

    reported = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "normal"}, "check_id": "check_fan_operation"},
    ).json()
    assert reported["state"]["next_action"]["check"]["id"] == "check_airflow_path"
    facts_event_id = reported["events"][-1]["id"]

    undone = client.post(
        f"/sessions/{session_id}/undo",
        json={"event_id": facts_event_id},
    )
    assert undone.status_code == 200, undone.text
    body = undone.json()
    assert body["state"]["next_action"]["check"]["id"] == "check_fan_operation"
    assert body["events"][-1]["type"] == "undo"


def test_undo_missing_event_returns_404(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    response = client.post(
        f"/sessions/{session_id}/undo",
        json={"event_id": 999999},
    )
    assert response.status_code == 404


def test_undo_event_from_other_session_returns_404(client: TestClient) -> None:
    first = _create_session(client, equipment_label="A")
    second = _create_session(client, equipment_label="B")
    reported = client.post(
        f"/sessions/{first['id']}/facts",
        json={"facts": {"fan_status": "normal"}},
    ).json()
    event_id = reported["events"][-1]["id"]

    response = client.post(
        f"/sessions/{second['id']}/undo",
        json={"event_id": event_id},
    )
    assert response.status_code == 404


def test_undo_already_undone_returns_409(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    reported = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "normal"}},
    ).json()
    event_id = reported["events"][-1]["id"]

    first = client.post(f"/sessions/{session_id}/undo", json={"event_id": event_id})
    assert first.status_code == 200
    second = client.post(f"/sessions/{session_id}/undo", json={"event_id": event_id})
    assert second.status_code == 409
    assert "already undone" in second.json()["detail"]


def test_undo_of_undo_event_returns_409(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    reported = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "normal"}},
    ).json()
    event_id = reported["events"][-1]["id"]
    undone = client.post(
        f"/sessions/{session_id}/undo",
        json={"event_id": event_id},
    ).json()
    undo_event_id = undone["events"][-1]["id"]

    response = client.post(
        f"/sessions/{session_id}/undo",
        json={"event_id": undo_event_id},
    )
    assert response.status_code == 409
    assert "cannot be undone" in response.json()["detail"]


def test_close_session_and_reject_further_writes(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    closed = client.post(f"/sessions/{session_id}/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    facts = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "normal"}},
    )
    assert facts.status_code == 409
    assert "closed" in facts.json()["detail"].lower()

    undo = client.post(f"/sessions/{session_id}/undo", json={"event_id": 1})
    assert undo.status_code == 409

    again = client.post(f"/sessions/{session_id}/close")
    assert again.status_code == 409


def test_concurrent_facts_writes_get_unique_seq(client: TestClient) -> None:
    session_id = _create_session(client)["id"]
    values = [10, 20, 30, 40, 50, 60, 70, 80]

    def post_load(value: int) -> int:
        response = client.post(
            f"/sessions/{session_id}/facts",
            json={"facts": {"load_percent": value}},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(post_load, value) for value in values]
        statuses = [future.result() for future in as_completed(futures)]

    assert statuses.count(200) == len(values)
    events = client.get(f"/sessions/{session_id}").json()["events"]
    seqs = [event["seq"] for event in events if event["type"] == "facts_reported"]
    assert sorted(seqs) == list(range(1, len(values) + 1))
    assert len(set(seqs)) == len(values)


def test_graph_change_returns_409(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = _create_session(
        client,
        initial_facts={"fan_status": "normal"},
    )["id"]

    original = loader.get_cached_graphs()["overtemperature"]
    reduced = FaultGraph.model_validate(
        {
            "fault_id": "overtemperature",
            "equipment": "vfd",
            "display_name": original.display_name,
            "fault_codes": original.fault_codes,
            "description": original.description,
            "fields": [
                field.model_dump(by_alias=True)
                for field in original.fields
                if field.name != "fan_status"
            ],
            "checks": [
                check.model_dump(by_alias=True)
                for check in original.checks
                if "fan_status" not in check.collects
            ],
            "causes": [
                cause.model_dump(by_alias=True)
                for cause in original.causes
                if cause.id != "cooling_fan_failure"
            ],
        }
    )

    def fake_graphs() -> dict[str, FaultGraph]:
        return {"overtemperature": reduced}

    monkeypatch.setitem(app.dependency_overrides, loader.get_graphs, fake_graphs)

    response = client.get(f"/sessions/{session_id}")
    assert response.status_code == 409
    assert "incompatible" in response.json()["detail"].lower()


def test_repository_events_are_append_only() -> None:
    repo_file = Path(__file__).resolve().parents[1] / "app" / "repository.py"
    text = repo_file.read_text(encoding="utf-8")
    assert "UPDATE events" not in text
    assert "DELETE FROM events" not in text

from __future__ import annotations

from fastapi.testclient import TestClient

from app.engine.engine import evaluate
from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.summary import build_summary, render_markdown
from app.models import Event
from datetime import datetime, timezone
from uuid import uuid4


def test_build_summary_root_cause_and_observation_fact() -> None:
    graph = load_graphs(DEFAULT_GRAPHS_DIR)["acs580_overtemperature"]
    session_id = uuid4()
    started = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    events = [
        Event(
            id=1,
            session_id=session_id,
            seq=1,
            type="observation",
            payload={
                "text": "The cooling fan is not running.",
                "check_id": "check_fan_operation",
                "extracted": {"fan_status": "not_running"},
                "unclear_fields": [],
                "rejected": [],
            },
            created_at=datetime(2026, 11, 17, 12, 1, tzinfo=timezone.utc),
        )
    ]
    state = evaluate(graph, {"fan_status": "not_running"})
    summary = build_summary(
        session_id=session_id,
        equipment_label="Line 3",
        started_at=started,
        graph=graph,
        events=events,
        state=state,
    )
    assert summary.status == "active"
    assert summary.root_cause is not None
    assert summary.root_cause.cause_id == "cooling_fan_failure"
    assert summary.escalation_reason is None
    assert len(summary.facts) == 1
    assert summary.facts[0].field == "fan_status"
    assert summary.facts[0].field_label == "Fan status"
    assert summary.facts[0].value == "not_running"
    assert summary.facts[0].value_label == "Not running"
    assert summary.facts[0].how == "observation"
    assert summary.facts[0].text == "The cooling fan is not running."
    assert any(c.used_for == "cause:cooling_fan_failure" for c in summary.citations)
    cite = next(c for c in summary.citations if c.used_for == "cause:cooling_fan_failure")
    assert cite.page == 543  # printed page, not PDF 541
    assert cite.short_name == "ABB ACS580 firmware manual"
    md = render_markdown(summary)
    assert "Cooling fan not operating" in md
    assert "typed observation" in md
    assert "Fan status: Not running" in md
    assert "fan_status" not in md
    assert "not_running" not in md


def test_summary_marks_undone_facts(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={
            "fault_id": "acs580_overtemperature",
            "equipment_label": "Line 7",
        },
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]

    observed = client.post(
        f"/sessions/{session_id}/observations",
        json={"text": "The cooling fan is not running."},
    )
    assert observed.status_code == 200, observed.text
    event_id = observed.json()["events"][-1]["id"]

    undone = client.post(
        f"/sessions/{session_id}/undo",
        json={"event_id": event_id},
    )
    assert undone.status_code == 200, undone.text

    summary = client.get(f"/sessions/{session_id}/summary")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["root_cause"] is None
    assert body["facts"]
    assert any(fact["undone"] is True for fact in body["facts"])
    assert all(
        fact["field"] != "fan_status" or fact["undone"]
        for fact in body["facts"]
    )


def test_summary_form_vs_observation_and_markdown(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={
            "fault_id": "acs580_overtemperature",
            "equipment_label": "Packer ACS580",
        },
    )
    session_id = created.json()["id"]

    form = client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "normal"}, "check_id": "check_fan_operation"},
    )
    assert form.status_code == 200, form.text

    typed = client.post(
        f"/sessions/{session_id}/observations",
        json={"text": "Vents look clear.", "check_id": "check_airflow_path"},
    )
    assert typed.status_code == 200, typed.text

    closed = client.post(f"/sessions/{session_id}/close")
    assert closed.status_code == 200, closed.text

    summary = client.get(f"/sessions/{session_id}/summary")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["status"] == "closed"
    assert body["closed_at"] is not None
    hows = {(f["field"], f["how"]) for f in body["facts"] if not f["undone"]}
    assert ("fan_status", "form") in hows
    assert ("airflow_obstruction", "observation") in hows
    assert any(
        f["text"] == "Vents look clear." for f in body["facts"] if f["how"] == "observation"
    )

    md = client.get(f"/sessions/{session_id}/summary?format=markdown")
    assert md.status_code == 200, md.text
    assert "text/markdown" in md.headers["content-type"]
    assert "Packer ACS580" in md.text
    assert "Fan status" in md.text
    assert "fan_status" not in md.text


def test_summary_citations_include_passage_field(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={
            "fault_id": "acs580_overtemperature",
            "equipment_label": "Line 4",
        },
    )
    session_id = created.json()["id"]
    client.post(
        f"/sessions/{session_id}/facts",
        json={"facts": {"fan_status": "not_running"}},
    )
    body = client.get(f"/sessions/{session_id}/summary").json()
    assert body["root_cause"] is not None
    assert body["citations"]
    for cite in body["citations"]:
        assert "passage" in cite
        # Without an ingested manual the passage stays null; the key must exist.
        assert cite["passage"] is None or isinstance(cite["passage"], str)


def _assert_no_internal_keys(obj: object, path: str = "$") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert not str(key).startswith("_"), f"internal key at {path}.{key}"
            _assert_no_internal_keys(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _assert_no_internal_keys(item, f"{path}[{index}]")


def test_summary_json_and_markdown_omit_internal_source_fields(
    client: TestClient,
) -> None:
    """Graph ``_todo`` annotations must never reach summary clients."""
    created = client.post(
        "/sessions",
        json={
            "fault_id": "acs580_overtemperature",
            "equipment_label": "Line 8",
        },
    )
    session_id = created.json()["id"]
    # motor_exceeds_drive_power.action_source carries a ``_todo`` in the graph JSON.
    client.post(
        f"/sessions/{session_id}/facts",
        json={
            "facts": {
                "fan_status": "normal",
                "airflow_obstruction": "none",
                "heatsink_condition": "clean",
                "ambient_above_derating_temp": "no",
                "motor_power_vs_drive": "exceeds",
            }
        },
    )
    body = client.get(f"/sessions/{session_id}/summary").json()
    assert body["root_cause"] is not None
    assert body["root_cause"]["cause_id"] == "motor_exceeds_drive_power"
    _assert_no_internal_keys(body["root_cause"]["source"])
    _assert_no_internal_keys(body["citations"])
    assert "_todo" not in body["root_cause"]["source"]

    md = client.get(f"/sessions/{session_id}/summary?format=markdown")
    assert md.status_code == 200, md.text
    assert "_todo" not in md.text
    assert "TODO(roota)" not in md.text


def test_session_view_sources_omit_internal_fields(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={
            "fault_id": "acs580_overtemperature",
            "equipment_label": "Line 2",
        },
    )
    assert created.status_code == 201, created.text
    state = created.json()["state"]
    check = state["next_action"]["check"]
    assert check is not None
    _assert_no_internal_keys(check)
    _assert_no_internal_keys(check["source"])


def test_summary_escalation_names_inconclusive_fan(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={
            "fault_id": "acs580_overtemperature",
            "equipment_label": "Line 9",
        },
    )
    session_id = created.json()["id"]
    client.post(
        f"/sessions/{session_id}/facts",
        json={
            "facts": {
                "fan_status": "noisy",
                "airflow_obstruction": "none",
                "heatsink_condition": "clean",
                "ambient_above_derating_temp": "no",
                "motor_power_vs_drive": "within",
            }
        },
    )
    summary = client.get(f"/sessions/{session_id}/summary").json()
    assert summary["root_cause"] is None
    assert summary["escalation_reason"] is not None
    assert "Cooling fan not operating" in summary["escalation_reason"]
    assert "Fan status: Noisy" in summary["escalation_reason"]
    assert "fan_status" not in summary["escalation_reason"]
    assert any(c["status"] == "inconclusive" for c in summary["causes"])
    fan = next(c for c in summary["causes"] if c["cause_id"] == "cooling_fan_failure")
    assert fan["because"] == ["Fan status: Noisy"]

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
    assert summary.outcome is not None
    assert summary.outcome[0].startswith("Root cause found: ")
    assert len(summary.facts) == 1
    assert summary.facts[0].field == "fan_status"
    assert summary.facts[0].field_label == "Fan"
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
    assert "Fan: Not running" in md
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
    assert "Fan: " in md.text
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
    """Graph maintainer notes and open questions must never reach summary clients."""
    created = client.post(
        "/sessions",
        json={
            "fault_id": "acs580_overtemperature",
            "equipment_label": "Line 8",
        },
    )
    session_id = created.json()["id"]
    # motor_exceeds_drive_power carries an open question in the graph JSON.
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
    assert "open_questions" not in body["root_cause"]
    assert "undersized drive" not in str(body)

    md = client.get(f"/sessions/{session_id}/summary?format=markdown")
    assert md.status_code == 200, md.text
    assert "undersized drive" not in md.text
    assert "open_questions" not in md.text


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
    outcome = " ".join(summary["outcome"])
    assert "Cooling fan not operating is still possible: fan running but noisy." in outcome
    assert "fan_status" not in outcome
    assert any(c["status"] == "inconclusive" for c in summary["causes"])
    fan = next(c for c in summary["causes"] if c["cause_id"] == "cooling_fan_failure")
    assert fan["status_label"] == "Inconclusive"
    assert fan["reason"] == "Fan running but noisy"


# --- Plain checklist reasons and "Not checked" ---


def _shipped_summary(facts: dict[str, object]):
    from app.engine.engine import evaluate
    from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
    from app.summary import build_summary

    graph = load_graphs(DEFAULT_GRAPHS_DIR)["acs580_overtemperature"]
    state = evaluate(graph, facts)
    return build_summary(
        session_id=uuid4(),
        equipment_label="Line 1",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        graph=graph,
        events=[],
        state=state,
    )


def _by_id(summary):
    return {cause.cause_id: cause for cause in summary.causes}


def test_causes_never_evaluated_after_a_root_cause_are_not_checked() -> None:
    summary = _shipped_summary({"fan_status": "not_running"})
    causes = _by_id(summary)
    assert causes["cooling_fan_failure"].status_label == "Confirmed"
    assert causes["cooling_fan_failure"].reason == "Fan not running"
    for cause_id in ("blocked_airflow", "load_above_derated_capacity", "motor_exceeds_drive_power"):
        assert causes[cause_id].status == "open"
        assert causes[cause_id].status_label == "Not checked"
        assert causes[cause_id].reason == "A root cause was found first"
    md = render_markdown(summary)
    assert (
        "- **Not checked** · Motor power exceeds drive power — "
        "A root cause was found first"
    ) in md
    assert "None" not in md
    assert "Open" not in md


def test_open_causes_mid_session_stay_open() -> None:
    summary = _shipped_summary({"fan_status": "normal"})
    causes = _by_id(summary)
    assert causes["blocked_airflow"].status_label == "Open"
    assert causes["cooling_fan_failure"].reason == "Fan running normally"


def test_checklist_reasons_name_the_specific_checks() -> None:
    summary = _shipped_summary(
        {
            "fan_status": "normal",
            "airflow_obstruction": "unclear",
            "heatsink_condition": "clean",
            "ambient_above_derating_temp": "yes",
            "load_within_derated_capacity": "yes",
            "motor_power_vs_drive": "within",
        }
    )
    causes = _by_id(summary)
    assert causes["blocked_airflow"].reason == (
        "Heatsink was clean; air flow not confirmed (technician wasn't sure)"
    )
    assert causes["cooling_fan_failure"].reason == "Fan running normally"
    assert causes["motor_exceeds_drive_power"].reason == (
        "Motor rating is within the drive's rating"
    )
    assert causes["load_above_derated_capacity"].reason == (
        "Room above the derating limit, but load within the derated rating"
    )
    checklist = render_markdown(summary).split("## Cause checklist")[1].split("\n## ")[0]
    assert "Technician wasn't sure" not in checklist
    assert ": Clean" not in checklist
    assert "- **Inconclusive** · Obstructed cooling air flow or dusty heatsink — Heatsink was clean" in checklist


def test_ruled_out_by_one_fact_names_only_that_check() -> None:
    summary = _shipped_summary({"ambient_above_derating_temp": "no"})
    assert _by_id(summary)["load_above_derated_capacity"].reason == (
        "Room below the derating limit"
    )


# --- Outcome in plain sentences ---


_ALL_CLEAR = {
    "fan_status": "normal",
    "airflow_obstruction": "none",
    "heatsink_condition": "clean",
    "ambient_above_derating_temp": "no",
    "motor_power_vs_drive": "within",
}


def test_root_cause_outcome_reads_as_sentences() -> None:
    summary = _shipped_summary({"fan_status": "not_running"})
    assert summary.outcome is not None
    first, others = summary.outcome
    assert first.startswith("Root cause found: Cooling fan not operating. Check fan operation")
    assert first.endswith("Source: ABB ACS580 firmware manual, A581 Fan, p. 543.")
    assert ".." not in first
    assert others == "The other three causes were not checked."


def test_root_cause_outcome_counts_ruled_out_and_not_checked_causes() -> None:
    summary = _shipped_summary(
        {"fan_status": "normal", "airflow_obstruction": "none", "heatsink_condition": "dusty"}
    )
    assert summary.outcome is not None
    assert summary.outcome[0].startswith(
        "Root cause found: Obstructed cooling air flow or dusty heatsink. "
    )
    assert summary.outcome[1] == (
        "Of the other three causes, one was ruled out and two were not checked."
    )


def test_escalation_with_an_unsure_check_names_it_and_suggests_rechecking() -> None:
    summary = _shipped_summary({**_ALL_CLEAR, "airflow_obstruction": "unclear"})
    assert summary.root_cause is None
    assert summary.outcome == [
        "None of the four documented causes could be confirmed. "
        "Three were ruled out by the checks. "
        "Obstructed cooling air flow or dusty heatsink is still possible: "
        "heatsink was clean, but you weren't sure about the air flow.",
        "Escalate to a senior technician or OEM support, "
        "and recheck the air path through the cabinet first.",
    ]
    md = render_markdown(summary)
    assert "## Escalation" in md
    assert "you weren't sure about the air flow" in md


def test_escalation_with_several_unsure_checks_rechecks_each_one() -> None:
    summary = _shipped_summary(
        {
            **_ALL_CLEAR,
            "ambient_above_derating_temp": "unclear",
            "load_within_derated_capacity": "unclear",
        }
    )
    assert summary.outcome is not None
    text = " ".join(summary.outcome)
    assert "Three were ruled out by the checks." in text
    assert "you weren't sure about the room temperature and the load." in text
    assert text.endswith(
        "recheck the ambient temperature at the drive and the load current "
        "against the derated rating first."
    )


def test_escalation_when_every_cause_is_ruled_out() -> None:
    summary = _shipped_summary(_ALL_CLEAR)
    assert summary.outcome == [
        "None of the four documented causes could be confirmed. "
        "All four were ruled out by the checks.",
        "Escalate to a senior technician or OEM support.",
    ]


def test_outcome_is_none_while_checks_remain() -> None:
    summary = _shipped_summary({"fan_status": "normal"})
    assert summary.outcome is None
    assert "Session still in progress." in render_markdown(summary)


def test_session_api_returns_the_outcome_sentences(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={"fault_id": "acs580_overtemperature", "equipment_label": "Line 4"},
    )
    session_id = created.json()["id"]
    assert created.json()["outcome"] is None
    reported = client.post(
        f"/sessions/{session_id}/facts", json={"facts": {"fan_status": "not_running"}}
    )
    assert reported.status_code == 200, reported.text
    assert reported.json()["outcome"][0].startswith(
        "Root cause found: Cooling fan not operating."
    )


def test_open_causes_have_no_reason_mid_session() -> None:
    summary = _shipped_summary({"fan_status": "normal"})
    assert _by_id(summary)["blocked_airflow"].reason is None


def test_joined_reasons_lowercase_every_part_after_the_first() -> None:
    summary = _shipped_summary(
        {"fan_status": "normal", "airflow_obstruction": "none", "heatsink_condition": "clean"}
    )
    assert _by_id(summary)["blocked_airflow"].reason == (
        "Air flow clear; heatsink was clean"
    )


def test_several_unsure_checks_join_in_lowercase() -> None:
    summary = _shipped_summary(
        {
            "fan_status": "normal",
            "airflow_obstruction": "unclear",
            "heatsink_condition": "unclear",
            "ambient_above_derating_temp": "no",
            "motor_power_vs_drive": "within",
        }
    )
    assert _by_id(summary)["blocked_airflow"].reason == (
        "Air flow not confirmed; heatsink condition not confirmed "
        "(technician wasn't sure)"
    )


def test_motor_root_cause_action_reads_plainly() -> None:
    summary = _shipped_summary({**_ALL_CLEAR, "motor_power_vs_drive": "exceeds"})
    assert summary.outcome is not None
    assert summary.outcome[0] == (
        "Root cause found: Motor power exceeds drive power. "
        "Resolve the mismatch between motor and drive ratings before returning to "
        "service: use a drive rated for the motor, or a motor within the drive's rating. "
        "The firmware manual's guidance is to check motor power against drive power. "
        "Source: ABB ACS580 firmware manual, 4210 IGBT overtemperature, p. 556."
    )


# --- Citations are listed once per passage ---


def test_citations_are_deduplicated_by_document_page_and_section() -> None:
    summary = _shipped_summary({**_ALL_CLEAR, "airflow_obstruction": "unclear"})
    keys = [(cite.doc_id, cite.page, cite.section) for cite in summary.citations]
    assert len(keys) == len(set(keys))
    # 4210 (p. 556) is cited by the fan, heatsink and motor checks; 4290 (p. 557)
    # by the air-flow and ambient checks. Each appears once, in first-use order.
    assert [cite.page for cite in summary.citations] == [556, 557]
    assert summary.citations[0].used_for == "check:check_fan_operation"
    assert summary.citations[1].used_for == "check:check_airflow_path"
    md = render_markdown(summary)
    assert md.count("4210 IGBT overtemperature, p. 556") == 1
    assert md.count("4290 Cooling, p. 557") == 1


def test_summary_api_lists_each_passage_once(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={"fault_id": "acs580_overtemperature", "equipment_label": "Line 2"},
    )
    session_id = created.json()["id"]
    client.post(f"/sessions/{session_id}/facts", json={"facts": _ALL_CLEAR})
    body = client.get(f"/sessions/{session_id}/summary").json()
    keys = [(c["doc_id"], c["page"], c["section"]) for c in body["citations"]]
    assert len(keys) == len(set(keys)) == 2


def test_not_checked_reasons_do_not_repeat_the_badge() -> None:
    for facts in ({"fan_status": "not_running"}, {**_ALL_CLEAR, "motor_power_vs_drive": "exceeds"}):
        for cause in _shipped_summary(facts).causes:
            assert not (cause.reason or "").startswith("Not checked")

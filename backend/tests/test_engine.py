from __future__ import annotations

import copy
from typing import Any

import pytest

from app.engine.engine import Truth, evaluate, evaluate_condition
from app.engine.schema import (
    UNCLEAR,
    AllCondition,
    AnyCondition,
    FaultGraph,
    FieldCondition,
)
from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs


@pytest.fixture(scope="module")
def overtemperature() -> FaultGraph:
    graphs = load_graphs(DEFAULT_GRAPHS_DIR)
    return graphs["overtemperature"]


def _status_map(state: Any) -> dict[str, str]:
    return {item.cause_id: item.status for item in state.causes}


def test_scenario_1_no_facts_next_is_cooling_fan_check(overtemperature: FaultGraph) -> None:
    state = evaluate(overtemperature, {})

    assert state.next_action.type == "check"
    assert state.next_action.check is not None
    assert state.next_action.check.id == "check_fan_operation"
    assert state.next_action.cause_id == "cooling_fan_failure"
    assert state.checks_completed == []


def test_scenario_2_fan_normal_rules_out_fan_next_airflow(
    overtemperature: FaultGraph,
) -> None:
    state = evaluate(overtemperature, {"fan_status": "normal"})

    assert _status_map(state)["cooling_fan_failure"] == "ruled_out"
    assert state.next_action.type == "check"
    assert state.next_action.check is not None
    assert state.next_action.check.id == "check_airflow_path"
    assert state.next_action.cause_id == "blocked_airflow"
    assert "check_fan_operation" in state.checks_completed


def test_scenario_3_redirection_promotes_excessive_load_duty_cycle_check(
    overtemperature: FaultGraph,
) -> None:
    state = evaluate(
        overtemperature,
        {
            "fan_status": "normal",
            "airflow_obstruction": "none",
            "heatsink_condition": "clean",
            "load_percent": 95,
        },
    )

    statuses = _status_map(state)
    assert statuses["cooling_fan_failure"] == "ruled_out"
    assert statuses["blocked_airflow"] == "ruled_out"
    assert statuses["excessive_load"] == "open"
    assert state.next_action.type == "check"
    assert state.next_action.check is not None
    assert state.next_action.check.id == "check_load_duty_cycle"
    assert state.next_action.cause_id == "excessive_load"


def test_volunteered_load_promotes_before_cooling_checks(
    overtemperature: FaultGraph,
) -> None:
    state = evaluate(overtemperature, {"load_percent": 95})

    statuses = _status_map(state)
    assert statuses["excessive_load"] == "open"
    assert statuses["cooling_fan_failure"] == "open"
    assert state.next_action.type == "check"
    assert state.next_action.check is not None
    assert state.next_action.check.id == "check_load_duty_cycle"
    assert state.next_action.cause_id == "excessive_load"


def test_load_confirmation_sustained_yes_root_cause(overtemperature: FaultGraph) -> None:
    state = evaluate(
        overtemperature,
        {"load_percent": 95, "high_load_sustained": "yes"},
    )

    assert _status_map(state)["excessive_load"] == "confirmed"
    assert state.next_action.type == "root_cause"
    assert state.next_action.cause_id == "excessive_load"
    assert state.next_action.message.startswith("Reduce mechanical/process load")
    assert state.next_action.source is not None
    assert state.next_action.source.doc_id == "TBD_MANUAL"


def test_load_confirmation_over_100_alone_root_cause(overtemperature: FaultGraph) -> None:
    state = evaluate(overtemperature, {"load_percent": 105})

    assert _status_map(state)["excessive_load"] == "confirmed"
    assert state.next_action.type == "root_cause"
    assert state.next_action.cause_id == "excessive_load"


def test_load_ruled_out_returns_to_highest_priority_open(
    overtemperature: FaultGraph,
) -> None:
    state = evaluate(
        overtemperature,
        {"load_percent": 95, "high_load_sustained": "no"},
    )

    statuses = _status_map(state)
    assert statuses["excessive_load"] == "ruled_out"
    assert statuses["cooling_fan_failure"] == "open"
    assert state.next_action.type == "check"
    assert state.next_action.check is not None
    assert state.next_action.check.id == "check_fan_operation"
    assert state.next_action.cause_id == "cooling_fan_failure"


def test_scenario_4_fan_unclear_need_info(overtemperature: FaultGraph) -> None:
    state = evaluate(overtemperature, {"fan_status": UNCLEAR})

    fan_field = next(field for field in overtemperature.fields if field.name == "fan_status")
    assert state.next_action.type == "need_info"
    assert state.next_action.fields == ["fan_status"]
    assert state.next_action.message == fan_field.ask
    assert state.next_action.cause_id == "cooling_fan_failure"


def test_all_causes_ruled_out_escalates(overtemperature: FaultGraph) -> None:
    state = evaluate(
        overtemperature,
        {
            "fan_status": "normal",
            "airflow_obstruction": "none",
            "heatsink_condition": "clean",
            "load_percent": 50,
            "ambient_temp_c": 25,
            "carrier_frequency_khz": 4,
        },
    )

    assert all(item.status == "ruled_out" for item in state.causes)
    assert state.next_action.type == "escalate"
    assert state.next_action.message == (
        "All documented causes for this fault have been ruled out."
    )


def test_confirmed_cause_root_cause_with_action_and_source(
    overtemperature: FaultGraph,
) -> None:
    state = evaluate(overtemperature, {"fan_status": "not_running"})

    cause = next(item for item in overtemperature.causes if item.id == "cooling_fan_failure")
    assert _status_map(state)["cooling_fan_failure"] == "confirmed"
    assert state.next_action.type == "root_cause"
    assert state.next_action.cause_id == "cooling_fan_failure"
    assert state.next_action.message == cause.corrective_action
    assert state.next_action.source == cause.action_source


def test_contradiction_escalates() -> None:
    graph = FaultGraph.model_validate(
        {
            "fault_id": "contradiction_demo",
            "equipment": "vfd",
            "display_name": "Contradiction demo",
            "fault_codes": ["X"],
            "description": "Synthetic graph for contradiction handling.",
            "fields": [
                {
                    "name": "flag_a",
                    "type": "enum",
                    "values": ["yes", "no", "unclear"],
                    "unit": None,
                    "description": "Flag A",
                    "ask": "Is flag A set?",
                },
                {
                    "name": "flag_b",
                    "type": "enum",
                    "values": ["yes", "no", "unclear"],
                    "unit": None,
                    "description": "Flag B",
                    "ask": "Is flag B set?",
                },
            ],
            "checks": [
                {
                    "id": "check_a",
                    "instruction": "Read A",
                    "reason": "Need A",
                    "collects": ["flag_a"],
                    "source": {"doc_id": "TBD_MANUAL", "section": "A", "page": None},
                },
                {
                    "id": "check_b",
                    "instruction": "Read B",
                    "reason": "Need B",
                    "collects": ["flag_b"],
                    "source": {"doc_id": "TBD_MANUAL", "section": "B", "page": None},
                },
            ],
            "causes": [
                {
                    "id": "both_ways",
                    "name": "Both ways",
                    "priority": 1,
                    "checks": ["check_a", "check_b"],
                    "ruled_out_when": {
                        "field": "flag_a",
                        "op": "eq",
                        "value": "yes",
                    },
                    "confirmed_when": {
                        "field": "flag_b",
                        "op": "eq",
                        "value": "yes",
                    },
                    "promote_when": None,
                    "corrective_action": "Impossible state.",
                    "action_source": {
                        "doc_id": "TBD_MANUAL",
                        "section": "fix",
                        "page": None,
                    },
                }
            ],
        }
    )

    state = evaluate(graph, {"flag_a": "yes", "flag_b": "yes"})

    assert _status_map(state)["both_ways"] == "contradiction"
    assert state.next_action.type == "escalate"
    assert state.next_action.cause_id == "both_ways"
    assert "Both ways" in state.next_action.message
    assert state.next_action.fields == ["flag_a", "flag_b"]


def test_completed_checks_never_reappear(overtemperature: FaultGraph) -> None:
    state = evaluate(
        overtemperature,
        {
            "fan_status": "normal",
            "airflow_obstruction": "none",
        },
    )

    assert "check_fan_operation" in state.checks_completed
    assert "check_airflow_path" in state.checks_completed
    assert state.next_action.type == "check"
    assert state.next_action.check is not None
    assert state.next_action.check.id == "check_heatsink_cleanliness"
    assert state.next_action.check.id not in state.checks_completed


def test_three_valued_all_with_unknown() -> None:
    condition = AllCondition(
        all=[
            FieldCondition(field="a", op="eq", value="yes"),
            FieldCondition(field="b", op="eq", value="yes"),
        ]
    )

    truth, because = evaluate_condition(condition, {"a": "yes"})
    assert truth is Truth.UNKNOWN
    assert because == []

    truth, because = evaluate_condition(condition, {"a": "yes", "b": "no"})
    assert truth is Truth.FALSE
    assert because == []

    truth, because = evaluate_condition(condition, {"a": "yes", "b": "yes"})
    assert truth is Truth.TRUE
    assert because == ["a", "b"]


def test_three_valued_any_with_unknown() -> None:
    condition = AnyCondition(
        any=[
            FieldCondition(field="a", op="eq", value="yes"),
            FieldCondition(field="b", op="eq", value="yes"),
        ]
    )

    truth, because = evaluate_condition(condition, {"a": "no"})
    assert truth is Truth.UNKNOWN
    assert because == []

    truth, because = evaluate_condition(condition, {"a": "no", "b": "no"})
    assert truth is Truth.FALSE
    assert because == []

    truth, because = evaluate_condition(condition, {"a": UNCLEAR, "b": "yes"})
    assert truth is Truth.TRUE
    assert because == ["b"]


def test_threshold_load_exactly_90(overtemperature: FaultGraph) -> None:
    state = evaluate(overtemperature, {"load_percent": 90})

    assert _status_map(state)["excessive_load"] == "open"
    assert state.next_action.type == "check"
    assert state.next_action.check is not None
    assert state.next_action.check.id == "check_load_duty_cycle"


def test_threshold_load_exactly_100(overtemperature: FaultGraph) -> None:
    open_state = evaluate(overtemperature, {"load_percent": 100})
    assert _status_map(open_state)["excessive_load"] == "open"

    ruled_out = evaluate(
        overtemperature,
        {"load_percent": 100, "high_load_sustained": "no"},
    )
    assert _status_map(ruled_out)["excessive_load"] == "ruled_out"

    confirmed = evaluate(
        overtemperature,
        {"load_percent": 100, "high_load_sustained": "yes"},
    )
    assert _status_map(confirmed)["excessive_load"] == "confirmed"
    assert confirmed.next_action.type == "root_cause"


def test_threshold_ambient_exactly_40(overtemperature: FaultGraph) -> None:
    state = evaluate(overtemperature, {"ambient_temp_c": 40})

    assert _status_map(state)["high_ambient_temperature"] == "confirmed"
    assert state.next_action.type == "root_cause"
    assert state.next_action.cause_id == "high_ambient_temperature"


def test_threshold_carrier_exactly_8(overtemperature: FaultGraph) -> None:
    state = evaluate(overtemperature, {"carrier_frequency_khz": 8})

    assert _status_map(state)["carrier_frequency_too_high"] == "ruled_out"


def test_unclear_on_number_field_need_info(overtemperature: FaultGraph) -> None:
    state = evaluate(
        overtemperature,
        {
            "fan_status": "normal",
            "airflow_obstruction": "none",
            "heatsink_condition": "clean",
            "load_percent": 50,
            "ambient_temp_c": UNCLEAR,
        },
    )

    ambient = next(
        field for field in overtemperature.fields if field.name == "ambient_temp_c"
    )
    assert state.next_action.type == "need_info"
    assert state.next_action.fields == ["ambient_temp_c"]
    assert state.next_action.message == ambient.ask
    assert state.next_action.cause_id == "high_ambient_temperature"


def test_unknown_fact_field_raises(overtemperature: FaultGraph) -> None:
    with pytest.raises(ValueError, match="unknown field 'not_a_field'"):
        evaluate(overtemperature, {"not_a_field": 1})


def test_wrong_type_fact_raises(overtemperature: FaultGraph) -> None:
    with pytest.raises(ValueError, match="invalid value for field 'load_percent'"):
        evaluate(overtemperature, {"load_percent": "ninety"})

    with pytest.raises(ValueError, match="invalid value for field 'fan_status'"):
        evaluate(overtemperature, {"fan_status": "spinning_fast"})


def test_input_facts_unchanged_after_evaluate(overtemperature: FaultGraph) -> None:
    facts = {"fan_status": "normal", "load_percent": 95}
    original = copy.deepcopy(facts)

    state = evaluate(overtemperature, facts)

    assert facts == original
    state.facts["fan_status"] = "noisy"
    assert facts["fan_status"] == "normal"


def test_promoted_and_ruled_out_not_current(overtemperature: FaultGraph) -> None:
    state = evaluate(
        overtemperature,
        {"load_percent": 95, "high_load_sustained": "no"},
    )

    assert _status_map(state)["excessive_load"] == "ruled_out"
    assert state.next_action.cause_id != "excessive_load"
    assert state.next_action.cause_id == "cooling_fan_failure"


def test_cause_status_exposes_promoted_flag(overtemperature: FaultGraph) -> None:
    # load_percent >= 90 promotes excessive_load while it remains open.
    state = evaluate(overtemperature, {"load_percent": 95})
    by_id = {item.cause_id: item for item in state.causes}
    assert by_id["excessive_load"].status == "open"
    assert by_id["excessive_load"].promoted is True
    assert by_id["cooling_fan_failure"].promoted is False
    # Open causes are listed in investigation order: promoted first.
    open_ids = [item.cause_id for item in state.causes if item.status == "open"]
    assert open_ids[0] == "excessive_load"


def test_two_promoted_causes_ordered_by_priority() -> None:
    graph = FaultGraph.model_validate(
        {
            "fault_id": "promote_order",
            "equipment": "vfd",
            "display_name": "Promote order",
            "fault_codes": ["P"],
            "description": "Two promoted open causes.",
            "fields": [
                {
                    "name": "score_a",
                    "type": "number",
                    "values": None,
                    "unit": None,
                    "description": "Score A",
                    "ask": "Score A?",
                },
                {
                    "name": "score_b",
                    "type": "number",
                    "values": None,
                    "unit": None,
                    "description": "Score B",
                    "ask": "Score B?",
                },
                {
                    "name": "detail_a",
                    "type": "enum",
                    "values": ["yes", "no", "unclear"],
                    "unit": None,
                    "description": "Detail A",
                    "ask": "Detail A?",
                },
                {
                    "name": "detail_b",
                    "type": "enum",
                    "values": ["yes", "no", "unclear"],
                    "unit": None,
                    "description": "Detail B",
                    "ask": "Detail B?",
                },
            ],
            "checks": [
                {
                    "id": "check_score_a",
                    "instruction": "Read score A",
                    "reason": "A",
                    "collects": ["score_a"],
                    "source": {"doc_id": "TBD_MANUAL", "section": "A", "page": None},
                },
                {
                    "id": "check_detail_a",
                    "instruction": "Read detail A",
                    "reason": "A detail",
                    "collects": ["detail_a"],
                    "source": {"doc_id": "TBD_MANUAL", "section": "A2", "page": None},
                },
                {
                    "id": "check_score_b",
                    "instruction": "Read score B",
                    "reason": "B",
                    "collects": ["score_b"],
                    "source": {"doc_id": "TBD_MANUAL", "section": "B", "page": None},
                },
                {
                    "id": "check_detail_b",
                    "instruction": "Read detail B",
                    "reason": "B detail",
                    "collects": ["detail_b"],
                    "source": {"doc_id": "TBD_MANUAL", "section": "B2", "page": None},
                },
            ],
            "causes": [
                {
                    "id": "cause_low_priority",
                    "name": "Low priority promoted",
                    "priority": 2,
                    "checks": ["check_score_a", "check_detail_a"],
                    "ruled_out_when": {
                        "field": "detail_a",
                        "op": "eq",
                        "value": "no",
                    },
                    "confirmed_when": {
                        "field": "detail_a",
                        "op": "eq",
                        "value": "yes",
                    },
                    "promote_when": {"field": "score_a", "op": "gte", "value": 10},
                    "corrective_action": "Fix A",
                    "action_source": {
                        "doc_id": "TBD_MANUAL",
                        "section": "fix A",
                        "page": None,
                    },
                },
                {
                    "id": "cause_high_priority",
                    "name": "High priority promoted",
                    "priority": 1,
                    "checks": ["check_score_b", "check_detail_b"],
                    "ruled_out_when": {
                        "field": "detail_b",
                        "op": "eq",
                        "value": "no",
                    },
                    "confirmed_when": {
                        "field": "detail_b",
                        "op": "eq",
                        "value": "yes",
                    },
                    "promote_when": {"field": "score_b", "op": "gte", "value": 10},
                    "corrective_action": "Fix B",
                    "action_source": {
                        "doc_id": "TBD_MANUAL",
                        "section": "fix B",
                        "page": None,
                    },
                },
            ],
        }
    )

    state = evaluate(graph, {"score_a": 10, "score_b": 10})

    assert state.next_action.type == "check"
    assert state.next_action.cause_id == "cause_high_priority"
    assert state.next_action.check is not None
    assert state.next_action.check.id == "check_detail_b"


def test_graph_gap_escalates() -> None:
    graph = FaultGraph.model_validate(
        {
            "fault_id": "graph_gap",
            "equipment": "vfd",
            "display_name": "Graph gap",
            "fault_codes": ["G"],
            "description": "Open cause with no resolving condition.",
            "fields": [
                {
                    "name": "observed",
                    "type": "enum",
                    "values": ["done", "unclear"],
                    "unit": None,
                    "description": "Observation complete",
                    "ask": "Is observation done?",
                }
            ],
            "checks": [
                {
                    "id": "check_observed",
                    "instruction": "Record observation",
                    "reason": "Need a fact",
                    "collects": ["observed"],
                    "source": {"doc_id": "TBD_MANUAL", "section": "Obs", "page": None},
                }
            ],
            "causes": [
                {
                    "id": "unresolvable",
                    "name": "Unresolvable",
                    "priority": 1,
                    "checks": ["check_observed"],
                    "ruled_out_when": None,
                    "confirmed_when": None,
                    "promote_when": None,
                    "corrective_action": "Cannot resolve from graph.",
                    "action_source": {
                        "doc_id": "TBD_MANUAL",
                        "section": "Gap",
                        "page": None,
                    },
                }
            ],
        }
    )

    state = evaluate(graph, {"observed": "done"})

    assert _status_map(state)["unresolvable"] == "open"
    assert state.next_action.type == "escalate"
    assert state.next_action.cause_id == "unresolvable"
    assert state.next_action.message == (
        "The documented checks for Unresolvable are complete but do not resolve it."
    )


# --- Review additions ---


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_number_fact_raises(overtemperature: FaultGraph, bad: float) -> None:
    # inf would confirm excessive_load; NaN fails every comparison and would
    # leave the cause neither confirmed nor ruled out.
    with pytest.raises(ValueError, match="expected a finite number"):
        evaluate(overtemperature, {"load_percent": bad})


def test_wrong_type_error_names_expected_values(overtemperature: FaultGraph) -> None:
    with pytest.raises(ValueError, match=r"expected one of \['normal'"):
        evaluate(overtemperature, {"fan_status": "spinning_fast"})


def test_output_independent_of_fact_order(overtemperature: FaultGraph) -> None:
    facts = {
        "fan_status": "normal",
        "airflow_obstruction": "partial",
        "heatsink_condition": "dusty",
        "load_percent": 105,
    }
    reversed_facts = dict(reversed(list(facts.items())))

    first = evaluate(overtemperature, facts).model_dump_json()
    second = evaluate(overtemperature, reversed_facts).model_dump_json()

    assert first == second


def test_proposal_demo_walkthrough(overtemperature: FaultGraph) -> None:
    # The demo script from the proposal, one technician observation at a time.
    steps: list[tuple[dict[str, Any], str, list[str]]] = [
        ({}, "check_fan_operation", []),
        ({"fan_status": "normal"}, "check_airflow_path", ["cooling_fan_failure"]),
        (
            {"airflow_obstruction": "none", "heatsink_condition": "clean"},
            "check_load_level",
            ["blocked_airflow", "cooling_fan_failure"],
        ),
        (
            {"load_percent": 95},
            "check_load_duty_cycle",
            ["blocked_airflow", "cooling_fan_failure"],
        ),
    ]
    facts: dict[str, Any] = {}
    for new_facts, expected_check, expected_ruled_out in steps:
        facts.update(new_facts)
        state = evaluate(overtemperature, facts)
        assert state.next_action.type == "check"
        assert state.next_action.check is not None
        assert state.next_action.check.id == expected_check
        ruled_out = sorted(c.cause_id for c in state.causes if c.status == "ruled_out")
        assert ruled_out == expected_ruled_out

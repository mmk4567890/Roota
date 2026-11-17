from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.engine.schema import FaultGraph
from app.graphs.loader import clear_graph_cache, get_graph, load_graphs
from tests.graph_fixtures import TEST_GRAPHS_DIR


def _minimal_graph(**overrides: Any) -> dict[str, Any]:
    graph: dict[str, Any] = {
        "fault_id": "sample",
        "equipment": "vfd",
        "display_name": "Sample",
        "fault_codes": ["X1"],
        "description": "Minimal valid graph for negative tests.",
        "fields": [
            {
                "name": "fan_status",
                "type": "enum",
                "values": ["normal", "not_running", "unclear"],
                "unit": None,
                "description": "Fan status",
                "ask": "How is the fan?",
            }
        ],
        "checks": [
            {
                "id": "check_fan",
                "instruction": "Check the fan.",
                "reason": "Fan matters.",
                "collects": ["fan_status"],
                "source": {
                    "doc_id": "TBD_MANUAL",
                    "section": "TODO(roota): sample source",
                    "page": None,
                },
            }
        ],
        "causes": [
            {
                "id": "fan_fail",
                "name": "Fan fail",
                "priority": 1,
                "checks": ["check_fan"],
                "ruled_out_when": {
                    "field": "fan_status",
                    "op": "eq",
                    "value": "normal",
                },
                "confirmed_when": None,
                "promote_when": None,
                "corrective_action": "Replace fan.",
                "action_source": {
                    "doc_id": "TBD_MANUAL",
                    "section": "TODO(roota): sample action source",
                    "page": None,
                },
            }
        ],
    }
    graph.update(overrides)
    return graph


def test_fixture_overtemperature_graph_loads() -> None:
    clear_graph_cache()
    graphs = load_graphs(TEST_GRAPHS_DIR)
    assert "overtemperature" in graphs
    graph = graphs["overtemperature"]
    assert graph.fault_id == "overtemperature"
    assert graph.equipment == "vfd"
    assert [cause.id for cause in graph.causes] == [
        "cooling_fan_failure",
        "blocked_airflow",
        "excessive_load",
        "high_ambient_temperature",
        "carrier_frequency_too_high",
    ]
    field_names = {field.name for field in graph.fields}
    assert {
        "fan_status",
        "airflow_obstruction",
        "heatsink_condition",
        "load_percent",
        "ambient_temp_c",
        "carrier_frequency_khz",
    }.issubset(field_names)
    assert get_graph("overtemperature") is graph


def test_rejects_duplicate_field_ids() -> None:
    payload = _minimal_graph()
    payload["fields"] = payload["fields"] + copy.deepcopy(payload["fields"])
    with pytest.raises(ValidationError, match="duplicate field"):
        FaultGraph.model_validate(payload)


def test_rejects_duplicate_check_ids() -> None:
    payload = _minimal_graph()
    payload["checks"] = payload["checks"] + copy.deepcopy(payload["checks"])
    with pytest.raises(ValidationError, match="duplicate check"):
        FaultGraph.model_validate(payload)


def test_rejects_duplicate_cause_ids() -> None:
    payload = _minimal_graph()
    payload["causes"] = payload["causes"] + copy.deepcopy(payload["causes"])
    with pytest.raises(ValidationError, match="duplicate cause"):
        FaultGraph.model_validate(payload)


def test_rejects_check_collects_unknown_field() -> None:
    payload = _minimal_graph()
    payload["checks"][0]["collects"] = ["unknown_field"]
    with pytest.raises(ValidationError, match="unknown field"):
        FaultGraph.model_validate(payload)


def test_rejects_cause_referencing_unknown_check() -> None:
    payload = _minimal_graph()
    payload["causes"][0]["checks"] = ["missing_check"]
    with pytest.raises(ValidationError, match="unknown check"):
        FaultGraph.model_validate(payload)


def test_rejects_condition_referencing_unknown_field() -> None:
    payload = _minimal_graph()
    payload["causes"][0]["ruled_out_when"] = {
        "field": "missing_field",
        "op": "eq",
        "value": "normal",
    }
    with pytest.raises(ValidationError, match="unknown field"):
        FaultGraph.model_validate(payload)


def test_rejects_enum_condition_value_not_in_values() -> None:
    payload = _minimal_graph()
    payload["causes"][0]["ruled_out_when"] = {
        "field": "fan_status",
        "op": "eq",
        "value": "spinning_fast",
    }
    with pytest.raises(ValidationError, match="not in enum field"):
        FaultGraph.model_validate(payload)


def test_rejects_enum_field_with_no_values() -> None:
    payload = _minimal_graph()
    payload["fields"][0]["values"] = []
    with pytest.raises(ValidationError, match="non-empty values"):
        FaultGraph.model_validate(payload)


def test_rejects_enum_field_without_unclear() -> None:
    payload = _minimal_graph()
    payload["fields"][0]["values"] = ["normal", "not_running"]
    with pytest.raises(ValidationError, match="unclear"):
        FaultGraph.model_validate(payload)


def test_get_faults_returns_overtemperature(client: TestClient) -> None:
    response = client.get("/faults")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    match = next(item for item in body if item["fault_id"] == "overtemperature")
    assert match["display_name"] == "Drive / heatsink overtemperature"
    assert "OH" in match["fault_codes"]
    assert match["description"]
    assert isinstance(match["fields"], list)
    assert match["fields"]
    field_names = {field["name"] for field in match["fields"]}
    assert "fan_status" in field_names
    fan = next(field for field in match["fields"] if field["name"] == "fan_status")
    assert fan["type"] == "enum"
    assert "normal" in fan["values"]



# --- Review additions: strict keys, type-aware conditions, reachability ---


def _set_ruled_out(payload: dict[str, Any], condition: Any) -> dict[str, Any]:
    payload["causes"][0]["ruled_out_when"] = condition
    return payload


def test_accepts_todo_annotations_on_any_object() -> None:
    payload = _minimal_graph(_todo="TODO(roota): graph-level note")
    payload["fields"][0]["_todo"] = "TODO(roota): field note"
    payload["checks"][0]["source"]["_todo"] = "TODO(roota): source note"
    payload["causes"][0]["ruled_out_when"]["_todo"] = "TODO(roota): threshold note"
    graph = FaultGraph.model_validate(payload)
    assert graph.todo == "TODO(roota): graph-level note"
    # Internal annotations stay on the model but never serialize to clients.
    dumped = graph.model_dump(mode="json", by_alias=True)
    assert "_todo" not in dumped
    assert "todo" not in dumped
    assert "_todo" not in dumped["checks"][0]["source"]
    assert "_todo" not in dumped["fields"][0]


def test_rejects_misspelled_cause_key() -> None:
    # A typo must not silently drop a rule (the cause could then never be ruled out).
    payload = _minimal_graph()
    payload["causes"][0]["ruled_out_whn"] = payload["causes"][0].pop("ruled_out_when")
    with pytest.raises(ValidationError, match="ruled_out_whn"):
        FaultGraph.model_validate(payload)


def test_rejects_misspelled_source_key() -> None:
    payload = _minimal_graph()
    payload["checks"][0]["source"]["pg"] = 12
    with pytest.raises(ValidationError, match="pg"):
        FaultGraph.model_validate(payload)


def test_rejects_ordering_op_on_enum_field() -> None:
    payload = _set_ruled_out(_minimal_graph(), {"field": "fan_status", "op": "gt", "value": "normal"})
    with pytest.raises(ValidationError, match="not valid for enum"):
        FaultGraph.model_validate(payload)


def test_rejects_non_numeric_value_on_number_field() -> None:
    payload = _minimal_graph()
    payload["fields"].append(
        {"name": "load_percent", "type": "number", "unit": "%", "description": "Load", "ask": "Load?"}
    )
    payload["checks"][0]["collects"] = ["fan_status", "load_percent"]
    _set_ruled_out(payload, {"field": "load_percent", "op": "lt", "value": "low"})
    with pytest.raises(ValidationError, match="must be a number"):
        FaultGraph.model_validate(payload)


def test_rejects_condition_testing_for_unclear() -> None:
    payload = _set_ruled_out(_minimal_graph(), {"field": "fan_status", "op": "eq", "value": "unclear"})
    with pytest.raises(ValidationError, match="must not test for 'unclear'"):
        FaultGraph.model_validate(payload)


def test_rejects_in_with_scalar_value() -> None:
    payload = _set_ruled_out(_minimal_graph(), {"field": "fan_status", "op": "in", "value": "normal"})
    with pytest.raises(ValidationError, match="non-empty list"):
        FaultGraph.model_validate(payload)


def test_rejects_list_value_without_in() -> None:
    payload = _set_ruled_out(_minimal_graph(), {"field": "fan_status", "op": "eq", "value": ["normal"]})
    with pytest.raises(ValidationError, match="single value"):
        FaultGraph.model_validate(payload)


def test_rejects_values_on_non_enum_field() -> None:
    payload = _minimal_graph()
    payload["fields"].append(
        {"name": "load_percent", "type": "number", "values": ["high"], "description": "Load", "ask": "Load?"}
    )
    with pytest.raises(ValidationError, match="must not declare values"):
        FaultGraph.model_validate(payload)


def test_rejects_condition_on_field_the_cause_cannot_collect() -> None:
    payload = _minimal_graph()
    payload["fields"].append(
        {"name": "ambient_temp_c", "type": "number", "unit": "°C", "description": "Ambient", "ask": "Ambient?"}
    )
    payload["checks"].append(
        {
            "id": "check_ambient",
            "instruction": "Measure ambient.",
            "reason": "Ambient matters.",
            "collects": ["ambient_temp_c"],
            "source": {"doc_id": "TBD_MANUAL", "section": "TODO(roota)", "page": None},
        }
    )
    # check_ambient exists in the graph, but is not one of fan_fail's checks.
    _set_ruled_out(payload, {"field": "ambient_temp_c", "op": "lt", "value": 40})
    with pytest.raises(ValidationError, match="none of the cause's checks collect"):
        FaultGraph.model_validate(payload)


def test_rejects_cause_without_checks() -> None:
    payload = _minimal_graph()
    payload["causes"][0]["checks"] = []
    with pytest.raises(ValidationError, match="checks"):
        FaultGraph.model_validate(payload)


def test_rejects_check_that_collects_nothing() -> None:
    payload = _minimal_graph()
    payload["checks"][0]["collects"] = []
    with pytest.raises(ValidationError, match="collects"):
        FaultGraph.model_validate(payload)


def test_rejects_duplicate_cause_priority() -> None:
    payload = _minimal_graph()
    second = copy.deepcopy(payload["causes"][0])
    second["id"] = "fan_fail_again"
    payload["causes"].append(second)
    with pytest.raises(ValidationError, match="duplicate cause priority"):
        FaultGraph.model_validate(payload)


def test_loader_names_the_invalid_file(tmp_path: Any) -> None:
    bad = _minimal_graph()
    bad["causes"][0]["checks"] = ["missing_check"]
    (tmp_path / "broken.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="broken.json"):
        load_graphs(tmp_path)
    clear_graph_cache()


def test_sample_load_promotion_redirects_without_confirming() -> None:
    # Scenario 3: near-rated load must redirect the investigation (promote),
    # not conclude it. Promotion and confirmation must therefore differ.
    graph = load_graphs(TEST_GRAPHS_DIR)["overtemperature"]
    excessive_load = next(cause for cause in graph.causes if cause.id == "excessive_load")
    assert excessive_load.promote_when is not None
    assert excessive_load.promote_when != excessive_load.confirmed_when
    assert excessive_load.checks == ["check_load_level", "check_load_duty_cycle"]

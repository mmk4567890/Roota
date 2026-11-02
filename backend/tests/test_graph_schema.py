from __future__ import annotations

import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.engine.schema import FaultGraph
from app.graphs.loader import DEFAULT_GRAPHS_DIR, clear_graph_cache, get_graph, load_graphs


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


def test_sample_overtemperature_graph_loads() -> None:
    clear_graph_cache()
    graphs = load_graphs(DEFAULT_GRAPHS_DIR)
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

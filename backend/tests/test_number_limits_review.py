"""Numbers outside float range or non-finite: rejected with a 422 or a
validation error, never a 500 and never a silently dead threshold."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.engine.schema import FaultGraph
from tests.graph_fixtures import TEST_GRAPHS_DIR
from app.parser.base import ParseResult
from app.routers import sessions

HUGE_INT_JSON = "1" + "0" * 400  # a valid JSON integer beyond float range


def _post_raw(client: TestClient, url: str, body: str) -> Any:
    return client.post(url, content=body, headers={"content-type": "application/json"})


def _session(client: TestClient) -> str:
    response = client.post(
        "/sessions", json={"fault_id": "overtemperature", "equipment_label": "Bay 1"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_facts_with_integer_beyond_float_range_is_422(client: TestClient) -> None:
    session_id = _session(client)

    response = _post_raw(
        client,
        f"/sessions/{session_id}/facts",
        '{"facts": {"load_percent": %s}}' % HUGE_INT_JSON,
    )

    assert response.status_code == 422
    assert "expected a finite number" in response.json()["detail"]
    assert client.get(f"/sessions/{session_id}").json()["events"] == []


def test_initial_facts_with_integer_beyond_float_range_is_422(client: TestClient) -> None:
    response = _post_raw(
        client,
        "/sessions",
        '{"fault_id": "overtemperature", "equipment_label": "Bay 1", '
        '"initial_facts": {"load_percent": %s}}' % HUGE_INT_JSON,
    )

    assert response.status_code == 422
    assert "load_percent" in response.json()["detail"]


def test_parser_integer_beyond_float_range_is_rejected_not_500(client: TestClient) -> None:
    class HugeNumberParser:
        def parse(self, text: str, graph: FaultGraph, expected_fields: list[str]) -> ParseResult:
            del text, graph, expected_fields
            return ParseResult(
                extracted={"load_percent": 10**400}, unclear_fields=[], rejected=[], notes=""
            )

    client.app.dependency_overrides[sessions.get_parser] = lambda: HugeNumberParser()
    session_id = _session(client)

    response = client.post(f"/sessions/{session_id}/observations", json={"text": "load"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert "load_percent" not in body["state"]["facts"]
    assert [item["field"] for item in body["parse"]["rejected"]] == ["load_percent"]
    assert "expected a finite number" in body["parse"]["rejected"][0]["reason"]


def _graph_with_threshold(value: object) -> dict:
    raw = json.loads(
        (Path(TEST_GRAPHS_DIR) / "overtemperature.json").read_text(encoding="utf-8")
    )
    graph = copy.deepcopy(raw)
    for cause in graph["causes"]:
        for rule_key in ("ruled_out_when", "confirmed_when", "promote_when"):
            rule = cause.get(rule_key)
            stack = [rule] if rule else []
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    if isinstance(node.get("value"), (int, float)) and not isinstance(
                        node.get("value"), bool
                    ):
                        node["value"] = value
                        return graph
                    stack.extend(node.values())
                elif isinstance(node, list):
                    stack.extend(node)
    raise AssertionError("overtemperature graph has no numeric threshold")


def test_graph_numeric_threshold_fixture_is_valid() -> None:
    FaultGraph.model_validate(_graph_with_threshold(90))


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_graph_rejects_non_finite_threshold(literal: str) -> None:
    # json.loads turns these literals into float nan / inf.
    graph = _graph_with_threshold(json.loads(literal))

    with pytest.raises(ValidationError, match="finite number"):
        FaultGraph.model_validate(graph)

from __future__ import annotations

import pytest

from app.engine.schema import FaultGraph
from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.parser.fake import KeywordParser


@pytest.fixture(scope="module")
def overtemperature() -> FaultGraph:
    return load_graphs(DEFAULT_GRAPHS_DIR)["overtemperature"]


@pytest.fixture
def parser() -> KeywordParser:
    return KeywordParser()


def test_fan_running_and_heatsink_clean(
    parser: KeywordParser, overtemperature: FaultGraph
) -> None:
    result = parser.parse(
        "The fan is running normally and the heatsink is clean.",
        overtemperature,
        ["fan_status"],
    )
    assert result.extracted["fan_status"] == "normal"
    assert result.extracted["heatsink_condition"] == "clean"
    assert "airflow_obstruction" not in result.extracted
    assert "load_percent" not in result.extracted


def test_fan_spinning_vents_packed_with_dust(
    parser: KeywordParser, overtemperature: FaultGraph
) -> None:
    result = parser.parse(
        "Fan is spinning fine but the vents are packed with dust.",
        overtemperature,
        ["fan_status"],
    )
    assert result.extracted["fan_status"] == "normal"
    assert result.extracted["airflow_obstruction"] == "blocked"
    assert result.extracted["heatsink_condition"] == "dusty"


def test_clean_airflow_close_to_rated_load_does_not_guess_percent(
    parser: KeywordParser, overtemperature: FaultGraph
) -> None:
    result = parser.parse(
        "Heatsink is clean and airflow is unobstructed, but the drive is "
        "operating close to its rated load.",
        overtemperature,
        ["heatsink_condition", "airflow_obstruction"],
    )
    assert result.extracted["heatsink_condition"] == "clean"
    assert result.extracted["airflow_obstruction"] == "none"
    # TODO(roota): do not invent a load_percent for "close to rated".
    assert "load_percent" not in result.extracted
    assert "TODO(roota)" in result.notes
    assert "rated" in result.notes.lower() or "load_percent" in result.notes


def test_fan_not_running(parser: KeywordParser, overtemperature: FaultGraph) -> None:
    result = parser.parse(
        "The cooling fan is not running.",
        overtemperature,
        ["fan_status"],
    )
    assert result.extracted["fan_status"] == "not_running"


def test_explicit_load_percent(
    parser: KeywordParser, overtemperature: FaultGraph
) -> None:
    result = parser.parse(
        "Drive load is at 95%.",
        overtemperature,
        ["load_percent"],
    )
    assert result.extracted["load_percent"] == 95


def test_unsupported_graph_returns_empty(
    parser: KeywordParser, overtemperature: FaultGraph
) -> None:
    other = overtemperature.model_copy(update={"fault_id": "other_fault"})
    result = parser.parse("fan is fine", other, ["fan_status"])
    assert result.extracted == {}
    assert "only supports" in result.notes

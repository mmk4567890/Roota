from __future__ import annotations

import pytest

from app.engine.schema import FaultGraph, UNCLEAR
from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.parser.keyword_parser import KeywordParser
from app.parser.validate import validate_parse


@pytest.fixture(scope="module")
def acs580() -> FaultGraph:
    return load_graphs(DEFAULT_GRAPHS_DIR)["acs580_overtemperature"]


@pytest.fixture
def parser() -> KeywordParser:
    return KeywordParser()


def test_fan_running_and_heatsink_clean(
    parser: KeywordParser, acs580: FaultGraph
) -> None:
    result = parser.parse(
        "The fan is running normally and the heatsink is clean.",
        acs580,
        ["fan_status"],
    )
    assert result.extracted["fan_status"] == "normal"
    assert result.extracted["heatsink_condition"] == "clean"
    assert "airflow_obstruction" not in result.extracted


def test_fan_spinning_vents_packed_with_dust(
    parser: KeywordParser, acs580: FaultGraph
) -> None:
    result = parser.parse(
        "Fan is spinning fine but the vents are packed with dust.",
        acs580,
        ["fan_status"],
    )
    assert result.extracted["fan_status"] == "normal"
    assert result.extracted["airflow_obstruction"] == "blocked"
    # Dusty vents say nothing about the heatsink: no inferred value.
    assert "heatsink_condition" not in result.extracted


def test_fan_not_running(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse("The cooling fan is not running.", acs580, ["fan_status"])
    assert result.extracted["fan_status"] == "not_running"


def test_fan_not_noisy_alone_is_unclear(
    parser: KeywordParser, acs580: FaultGraph
) -> None:
    raw = parser.parse("The fan is not noisy.", acs580, ["fan_status"])
    assert raw.extracted["fan_status"] == UNCLEAR
    parsed = validate_parse(raw, acs580)
    assert "fan_status" not in parsed.extracted
    assert parsed.unclear_fields == ["fan_status"]


def test_fan_running_and_not_noisy_is_normal(
    parser: KeywordParser, acs580: FaultGraph
) -> None:
    result = parser.parse(
        "The fan is running and not noisy.", acs580, ["fan_status"]
    )
    assert result.extracted["fan_status"] == "normal"


def test_fan_spinning_not_noisy_is_normal(
    parser: KeywordParser, acs580: FaultGraph
) -> None:
    result = parser.parse("Fan is spinning, not noisy.", acs580, ["fan_status"])
    assert result.extracted["fan_status"] == "normal"


def test_heatsink_no_dust_is_clean(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse("Heatsink has no dust.", acs580, ["heatsink_condition"])
    assert result.extracted["heatsink_condition"] == "clean"


def test_air_path_open(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse("The air path is open.", acs580, ["airflow_obstruction"])
    assert result.extracted["airflow_obstruction"] == "none"


def test_vents_partly_blocked(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse("Vents are partly blocked.", acs580, ["airflow_obstruction"])
    assert result.extracted["airflow_obstruction"] == "partial"


def test_ambient_cool_room(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse("Room is cool.", acs580, ["ambient_above_derating_temp"])
    assert result.extracted["ambient_above_derating_temp"] == "no"


def test_ambient_below_40(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse(
        "Ambient is about 35 C.", acs580, ["ambient_above_derating_temp"]
    )
    assert result.extracted["ambient_above_derating_temp"] == "no"


def test_ambient_above_50(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse(
        "Ambient is about 55 C.", acs580, ["ambient_above_derating_temp"]
    )
    assert result.extracted["ambient_above_derating_temp"] == "yes"


def test_ambient_between_40_and_50_is_unclear(
    parser: KeywordParser, acs580: FaultGraph
) -> None:
    raw = parser.parse(
        "Ambient is about 45 C.", acs580, ["ambient_above_derating_temp"]
    )
    assert raw.extracted["ambient_above_derating_temp"] == UNCLEAR
    assert "40" in raw.notes and "50" in raw.notes
    assert "derating" in raw.notes.lower()
    assert "frame" in raw.notes.lower()
    assert "ip" in raw.notes.lower()

    parsed = validate_parse(raw, acs580)
    assert "ambient_above_derating_temp" not in parsed.extracted
    assert parsed.unclear_fields == ["ambient_above_derating_temp"]
    assert parsed.notes == raw.notes


def test_ambient_exactly_40_is_unclear(
    parser: KeywordParser, acs580: FaultGraph
) -> None:
    result = parser.parse("Ambient temperature 40 C.", acs580, [])
    assert result.extracted["ambient_above_derating_temp"] == UNCLEAR


def test_ambient_exactly_50_is_unclear(
    parser: KeywordParser, acs580: FaultGraph
) -> None:
    # Above 50 = yes; at 50 the limit still depends on frame/IP.
    result = parser.parse("Ambient is 50 C.", acs580, [])
    assert result.extracted["ambient_above_derating_temp"] == UNCLEAR


def test_motor_exceeds_drive_kw(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse(
        "Motor is 75 kW, drive is 55 kW.", acs580, ["motor_power_vs_drive"]
    )
    assert result.extracted["motor_power_vs_drive"] == "exceeds"


def test_motor_matches_drive(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse(
        "Motor matches the drive.", acs580, ["motor_power_vs_drive"]
    )
    assert result.extracted["motor_power_vs_drive"] == "within"


def test_motor_vs_drive_hp(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse(
        "Motor is 100 hp and the drive is 50 hp.", acs580, ["motor_power_vs_drive"]
    )
    assert result.extracted["motor_power_vs_drive"] == "exceeds"


def test_load_within_derated(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse(
        "Load is within the derated rating.",
        acs580,
        ["load_within_derated_capacity"],
    )
    assert result.extracted["load_within_derated_capacity"] == "yes"


def test_full_load_in_heat(parser: KeywordParser, acs580: FaultGraph) -> None:
    result = parser.parse(
        "Running at full load in this heat.",
        acs580,
        ["load_within_derated_capacity"],
    )
    assert result.extracted["load_within_derated_capacity"] == "no"


def test_unsupported_graph_returns_empty(
    parser: KeywordParser, acs580: FaultGraph
) -> None:
    renamed = [
        field.model_copy(update={"name": f"other_{field.name}"})
        for field in acs580.fields
    ]
    other = acs580.model_copy(update={"fault_id": "other_fault", "fields": renamed})
    result = parser.parse("fan is fine", other, ["other_fan_status"])
    assert result.extracted == {}
    assert "knows none of the fields of fault_id 'other_fault'" in result.notes

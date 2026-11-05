from __future__ import annotations

import math

import pytest

from app.engine.schema import FaultGraph
from app.graphs.loader import load_graphs
from tests.graph_fixtures import TEST_GRAPHS_DIR
from app.parser.base import ParseError, ParseResult, RejectedValue
from app.parser.validate import validate_parse


@pytest.fixture(scope="module")
def overtemperature() -> FaultGraph:
    graphs = load_graphs(TEST_GRAPHS_DIR)
    return graphs["overtemperature"]


def _result(
    *,
    extracted: dict | None = None,
    unclear_fields: list[str] | None = None,
    rejected: list[RejectedValue] | None = None,
    notes: str = "",
) -> ParseResult:
    return ParseResult(
        extracted=extracted or {},
        unclear_fields=unclear_fields or [],
        rejected=rejected or [],
        notes=notes,
    )


def test_accepts_valid_enum_and_number(overtemperature: FaultGraph) -> None:
    parsed = validate_parse(
        _result(extracted={"fan_status": "normal", "load_percent": 95}),
        overtemperature,
    )
    assert parsed.extracted == {"fan_status": "normal", "load_percent": 95}
    assert parsed.unclear_fields == []
    assert parsed.rejected == []


def test_unknown_field_rejected_not_in_extracted(overtemperature: FaultGraph) -> None:
    parsed = validate_parse(
        _result(extracted={"not_a_field": "x", "fan_status": "normal"}),
        overtemperature,
    )
    assert "not_a_field" not in parsed.extracted
    assert parsed.extracted == {"fan_status": "normal"}
    assert len(parsed.rejected) == 1
    assert parsed.rejected[0].field == "not_a_field"
    assert "unknown field 'not_a_field'" in parsed.rejected[0].reason


def test_bad_enum_rejected_not_added_to_unclear(overtemperature: FaultGraph) -> None:
    parsed = validate_parse(
        _result(extracted={"fan_status": "spinning_fast"}),
        overtemperature,
    )
    assert "fan_status" not in parsed.extracted
    assert "fan_status" not in parsed.unclear_fields
    assert len(parsed.rejected) == 1
    assert parsed.rejected[0].field == "fan_status"
    assert parsed.rejected[0].value == "spinning_fast"


def test_bad_number_rejected(overtemperature: FaultGraph) -> None:
    for bad in ("ninety", True, float("nan"), float("inf"), -float("inf")):
        parsed = validate_parse(
            _result(extracted={"load_percent": bad}),
            overtemperature,
        )
        assert "load_percent" not in parsed.extracted
        assert "load_percent" not in parsed.unclear_fields
        assert any(item.field == "load_percent" for item in parsed.rejected)


def test_no_string_to_number_coercion(overtemperature: FaultGraph) -> None:
    parsed = validate_parse(
        _result(extracted={"load_percent": "95"}),
        overtemperature,
    )
    assert "load_percent" not in parsed.extracted
    assert parsed.rejected[0].field == "load_percent"


def test_unclear_in_extracted_moves_to_unclear_fields(
    overtemperature: FaultGraph,
) -> None:
    parsed = validate_parse(
        _result(extracted={"fan_status": "unclear", "load_percent": 40}),
        overtemperature,
    )
    assert "fan_status" not in parsed.extracted
    assert parsed.unclear_fields == ["fan_status"]
    assert parsed.extracted == {"load_percent": 40}
    assert parsed.rejected == []


def test_unknown_field_in_unclear_fields_rejected(overtemperature: FaultGraph) -> None:
    parsed = validate_parse(
        _result(unclear_fields=["ghost_field", "fan_status"]),
        overtemperature,
    )
    assert parsed.unclear_fields == ["fan_status"]
    assert any(
        item.field == "ghost_field" and "unknown field" in item.reason
        for item in parsed.rejected
    )


def test_same_field_in_extracted_and_unclear_raises(
    overtemperature: FaultGraph,
) -> None:
    with pytest.raises(ParseError, match="contradictory"):
        validate_parse(
            _result(
                extracted={"fan_status": "normal"},
                unclear_fields=["fan_status"],
            ),
            overtemperature,
        )


def test_unclear_value_then_also_listed_is_not_contradiction(
    overtemperature: FaultGraph,
) -> None:
    # Moving "unclear" into unclear_fields when it is already listed is fine.
    parsed = validate_parse(
        _result(
            extracted={"fan_status": "unclear"},
            unclear_fields=["fan_status"],
        ),
        overtemperature,
    )
    assert parsed.extracted == {}
    assert parsed.unclear_fields == ["fan_status"]


def test_structurally_broken_raises_parse_error(overtemperature: FaultGraph) -> None:
    with pytest.raises(ParseError, match="ParseResult or dict"):
        validate_parse("not a result", overtemperature)

    with pytest.raises(ParseError, match="extracted must be a dict"):
        validate_parse(
            {
                "extracted": ["nope"],
                "unclear_fields": [],
                "rejected": [],
                "notes": "",
            },
            overtemperature,
        )

    with pytest.raises(ParseError, match="missing required keys"):
        validate_parse({"extracted": {}}, overtemperature)


def test_preserves_prior_rejected_entries(overtemperature: FaultGraph) -> None:
    prior = RejectedValue(field="pre", value=1, reason="already rejected")
    parsed = validate_parse(
        _result(extracted={"fan_status": "normal"}, rejected=[prior]),
        overtemperature,
    )
    assert parsed.rejected[0] == prior
    assert parsed.extracted == {"fan_status": "normal"}


def test_finite_boundary_numbers_accepted(overtemperature: FaultGraph) -> None:
    parsed = validate_parse(
        _result(extracted={"load_percent": 0, "ambient_temp_c": -40.5}),
        overtemperature,
    )
    assert parsed.extracted["load_percent"] == 0
    assert parsed.extracted["ambient_temp_c"] == -40.5
    assert math.isfinite(parsed.extracted["ambient_temp_c"])

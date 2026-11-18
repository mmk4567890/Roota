from __future__ import annotations

import pytest

from app.retrieval.passage import reflow_passage


def test_reflow_joins_soft_line_breaks_into_paragraphs() -> None:
    raw = (
        "4210 IGBT overtemperature Estimated drive IGBT\n"
        "temperature is excessive.\n"
        "Check air flow and fan operation.\n"
    )
    assert reflow_passage(raw) == (
        "4210 IGBT overtemperature Estimated drive IGBT "
        "temperature is excessive. Check air flow and fan operation."
    )


def test_reflow_keeps_list_items_on_their_own_lines() -> None:
    raw = (
        "Check the following:\n"
        "- inlet clear\n"
        "- outlet clear\n"
        "Then power the drive.\n"
    )
    assert reflow_passage(raw) == (
        "Check the following:\n\n"
        "- inlet clear\n\n"
        "- outlet clear\n\n"
        "Then power the drive."
    )


def test_reflow_drops_trailing_table_header_fragment() -> None:
    raw = (
        "4290 Cooling Check drive module cooling air flow and fan operation.\n"
        "Code (hex) Fault / Aux. code Cause What to do"
    )
    assert reflow_passage(raw) == (
        "4290 Cooling Check drive module cooling air flow and fan operation."
    )
    assert "Code (hex)" not in reflow_passage(raw)


def test_reflow_rejoins_hyphenated_line_breaks() -> None:
    raw = "tempera-\nture is excessive."
    assert reflow_passage(raw) == "temperature is excessive."


ENTRY = "4210 IGBT overtemperature Check motor power against drive power."


@pytest.mark.parametrize(
    "fragment",
    [
        "Code (hex)",
        "Code (hex) Fault",
        "Code (hex) Fault / Aux.",
        "Code (hex) Fault/Aux. code",
        "Code (hex) Fault / Aux. code Cause",
        "Code (hex) Fault / Aux. code Cause What to do",
        "Fault / Aux. code Cause What to do",
    ],
)
@pytest.mark.parametrize("separator", [" ", "\n"])
def test_reflow_drops_any_trailing_table_header_fragment(
    fragment: str, separator: str
) -> None:
    assert reflow_passage(ENTRY + separator + fragment) == ENTRY


def test_reflow_drops_a_bare_code_hex_tail() -> None:
    raw = (
        "4210 IGBT overtemperature Estimated drive IGBT temperature is excessive. "
        "Check motor power against drive power. Code (hex)"
    )
    cleaned = reflow_passage(raw)
    assert cleaned.endswith("Check motor power against drive power.")
    assert "Code (hex)" not in cleaned


def test_reflow_keeps_code_hex_in_the_middle_of_a_passage() -> None:
    raw = "See the Code (hex) column for the fault number. Check the fan."
    assert reflow_passage(raw) == raw


def test_reflow_keeps_a_word_that_only_ends_like_the_header() -> None:
    raw = "Replace the fan if the cause is clear, then what to do"
    assert reflow_passage(raw) == raw

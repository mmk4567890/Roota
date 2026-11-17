from __future__ import annotations

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

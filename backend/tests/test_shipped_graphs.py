"""The graphs Roota ships: real knowledge only, every citation checkable."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.engine.engine import evaluate
from app.engine.schema import FaultGraph, Source
from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.parser.keyword_parser import KeywordParser

MANUAL_DOC_ID = "abb_acs580_fw"
MANUAL_PAGES = 632
MANUAL_PDF = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "manuals"
    / "ABB_ACS580_firmware_manual_3AXD50000016097_RevJ.pdf"
)

COOLING_OK = {
    "fan_status": "normal",
    "airflow_obstruction": "none",
    "heatsink_condition": "clean",
}


@pytest.fixture(scope="module")
def acs580() -> FaultGraph:
    return load_graphs(DEFAULT_GRAPHS_DIR)["acs580_overtemperature"]


def _sources(graph: FaultGraph) -> list[tuple[str, Source]]:
    found = [(f"check {check.id}", check.source) for check in graph.checks]
    found += [(f"cause {cause.id}", cause.action_source) for cause in graph.causes]
    return found


# --- what ships ---


def test_only_real_graphs_ship() -> None:
    graphs = load_graphs(DEFAULT_GRAPHS_DIR)
    assert sorted(graphs) == ["acs580_overtemperature"]
    # The generic placeholder graph is a test fixture, never shipped.
    assert not (Path(DEFAULT_GRAPHS_DIR) / "overtemperature.json").exists()


def test_every_citation_is_the_acs580_manual(acs580: FaultGraph) -> None:
    for where, source in _sources(acs580):
        assert source.doc_id == MANUAL_DOC_ID, where
        assert source.page is not None and 1 <= source.page <= MANUAL_PAGES, where
        assert source.section.startswith("Fault tracing: "), where


def test_fault_codes_are_the_manuals(acs580: FaultGraph) -> None:
    assert acs580.fault_codes == ["4210", "42F1", "4290", "4310", "A4A1", "A4F6", "A4A9", "A4B0"]


def test_no_invented_thresholds(acs580: FaultGraph) -> None:
    # The firmware manual gives no load-percent, ambient or carrier thresholds
    # for these faults, so the graph has no numeric fields to compare.
    assert all(field.type == "enum" for field in acs580.fields)
    assert {cause.id for cause in acs580.causes} == {
        "cooling_fan_failure",
        "blocked_airflow",
        "load_above_derated_capacity",
        "motor_exceeds_drive_power",
    }


# --- the cited pages say what the graph quotes ---

QUOTES = {
    # PDF page -> phrases the graph relies on (whitespace-normalised)
    554: [
        "4210 IGBT overtemperature",
        "Check air flow and fan operation.",
        "Check heatsink fins for dust pick-up.",
        "Check motor power against drive power.",
    ],
    555: [
        "4290 Cooling",
        "ensure that load current does not exceed derated load capacity of drive",
        "Check drive module cooling air flow and fan operation.",
        "heatsink of drive module for dust pick-up. Clean whenever necessary.",
        "42F1 IGBT temperature",
        "4310 Excess temperature",
    ],
    541: [
        "A581 Fan",
        "Check fan operation and connection.",
        "Replace fan if faulty.",
    ],
}


@pytest.fixture(scope="module")
def manual_pages() -> dict[int, str]:
    if not MANUAL_PDF.is_file():
        pytest.skip(f"ACS580 manual not present at {MANUAL_PDF} (gitignored; see README Manuals)")
    from pypdf import PdfReader

    reader = PdfReader(str(MANUAL_PDF))
    assert len(reader.pages) == MANUAL_PAGES
    return {
        page: " ".join((reader.pages[page - 1].extract_text() or "").split())
        for page in {source.page for _, source in _sources(load_graphs(DEFAULT_GRAPHS_DIR)["acs580_overtemperature"])}
        | set(QUOTES)
    }


@pytest.mark.parametrize("page", sorted(QUOTES))
def test_cited_page_contains_quoted_text(manual_pages: dict[int, str], page: int) -> None:
    for phrase in QUOTES[page]:
        assert phrase in manual_pages[page], f"p.{page} lacks {phrase!r}"


def test_every_cited_page_is_a_fault_tracing_page(
    acs580: FaultGraph, manual_pages: dict[int, str]
) -> None:
    for where, source in _sources(acs580):
        assert "Fault tracing" in manual_pages[source.page], where
        # The section names the fault code whose entry is on that page.
        code = source.section.removeprefix("Fault tracing: ").split(" ")[0]
        assert code in manual_pages[source.page], f"{where}: {code} not on p.{source.page}"


# --- the walk a technician sees ---


def test_starts_with_the_fan(acs580: FaultGraph) -> None:
    action = evaluate(acs580, {}).next_action
    assert action.type == "check"
    assert action.check is not None and action.check.id == "check_fan_operation"


def test_fan_not_running_is_the_root_cause(acs580: FaultGraph) -> None:
    action = evaluate(acs580, {"fan_status": "not_running"}).next_action
    assert action.type == "root_cause"
    assert action.cause_id == "cooling_fan_failure"
    assert action.source is not None and action.source.page == 541


def test_noisy_fan_escalates_instead_of_guessing(acs580: FaultGraph) -> None:
    # The manual does not say whether a noisy fan is faulty.
    action = evaluate(acs580, {"fan_status": "noisy"}).next_action
    assert action.type == "escalate"
    assert action.cause_id == "cooling_fan_failure"


def test_dusty_heatsink_confirms_airflow_cause(acs580: FaultGraph) -> None:
    state = evaluate(
        acs580,
        {"fan_status": "normal", "airflow_obstruction": "none", "heatsink_condition": "dusty"},
    )
    assert state.next_action.type == "root_cause"
    assert state.next_action.cause_id == "blocked_airflow"


def test_ambient_below_derating_skips_the_derated_load_check(acs580: FaultGraph) -> None:
    state = evaluate(acs580, {**COOLING_OK, "ambient_above_derating_temp": "no"})
    by_id = {cause.cause_id: cause.status for cause in state.causes}
    assert by_id["load_above_derated_capacity"] == "ruled_out"
    assert state.next_action.check is not None
    assert state.next_action.check.id == "check_motor_vs_drive_power"


def test_hot_ambient_asks_for_derated_load(acs580: FaultGraph) -> None:
    action = evaluate(acs580, {**COOLING_OK, "ambient_above_derating_temp": "yes"}).next_action
    assert action.check is not None and action.check.id == "check_derated_load"


def test_hot_ambient_and_load_over_derated_capacity_is_the_root_cause(acs580: FaultGraph) -> None:
    action = evaluate(
        acs580,
        {**COOLING_OK, "ambient_above_derating_temp": "yes", "load_within_derated_capacity": "no"},
    ).next_action
    assert action.type == "root_cause"
    assert action.cause_id == "load_above_derated_capacity"


def test_hot_ambient_within_derated_capacity_moves_on(acs580: FaultGraph) -> None:
    action = evaluate(
        acs580,
        {**COOLING_OK, "ambient_above_derating_temp": "yes", "load_within_derated_capacity": "yes"},
    ).next_action
    assert action.check is not None and action.check.id == "check_motor_vs_drive_power"


def test_motor_exceeding_drive_power_is_the_root_cause(acs580: FaultGraph) -> None:
    action = evaluate(
        acs580,
        {**COOLING_OK, "ambient_above_derating_temp": "no", "motor_power_vs_drive": "exceeds"},
    ).next_action
    assert action.type == "root_cause"
    assert action.cause_id == "motor_exceeds_drive_power"


def test_everything_ruled_out_escalates(acs580: FaultGraph) -> None:
    action = evaluate(
        acs580,
        {**COOLING_OK, "ambient_above_derating_temp": "no", "motor_power_vs_drive": "within"},
    ).next_action
    assert action.type == "escalate"


def test_unclear_answer_asks_again_instead_of_guessing(acs580: FaultGraph) -> None:
    action = evaluate(acs580, {"fan_status": "unclear"}).next_action
    assert action.type == "need_info"
    assert action.fields == ["fan_status"]


# --- offline parsing and the API ---


def test_keyword_parser_reads_the_cooling_fields(acs580: FaultGraph) -> None:
    result = KeywordParser().parse(
        "Fan is running normally but the heatsink fins are full of dust.", acs580, []
    )
    assert result.extracted == {"fan_status": "normal", "heatsink_condition": "dusty"}


def test_keyword_parser_ignores_bare_load_percent(acs580: FaultGraph) -> None:
    # A bare load percentage is not one of the ACS580 enum fields; do not invent
    # load_within_derated_capacity from it.
    result = KeywordParser().parse("Drive load is 95%.", acs580, [])
    assert result.extracted == {}
    assert "load_within_derated_capacity" not in result.extracted


def test_api_session_on_the_real_graph(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={"fault_id": "acs580_overtemperature", "equipment_label": "Line 3 ACS580"},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]

    observed = client.post(
        f"/sessions/{session_id}/observations",
        json={"text": "The cooling fan is not running.", "check_id": "check_fan_operation"},
    )

    assert observed.status_code == 200, observed.text
    action = observed.json()["state"]["next_action"]
    assert action["type"] == "root_cause"
    assert action["cause_id"] == "cooling_fan_failure"
    assert action["source"]["doc_id"] == MANUAL_DOC_ID
    assert action["source"]["page"] == 541

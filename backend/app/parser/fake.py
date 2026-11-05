from __future__ import annotations

import re

from app.engine.schema import FaultGraph
from app.parser.base import ParseResult

# Field names the keyword rules can fill. A graph is supported when it has at
# least one of them (the ACS580 overtemperature graph shares the cooling ones).
KNOWN_FIELDS = frozenset(
    {
        "fan_status",
        "airflow_obstruction",
        "heatsink_condition",
        "load_percent",
        "high_load_sustained",
        "ambient_temp_c",
        "carrier_frequency_khz",
    }
)


class KeywordParser:
    """Deterministic rule-based parser for tests and offline demos.

    Fills only the field names in KNOWN_FIELDS, for any graph that has them.
    Rules are intentionally narrow so they do not invent values the technician
    did not state.
    """

    def parse(
        self,
        text: str,
        graph: FaultGraph,
        expected_fields: list[str],
    ) -> ParseResult:
        del expected_fields  # Keyword rules scan the whole utterance.
        graph_fields = {field.name for field in graph.fields}
        if not graph_fields & KNOWN_FIELDS:
            return ParseResult(
                extracted={},
                unclear_fields=[],
                rejected=[],
                notes=(
                    f"KeywordParser knows none of the fields of fault_id "
                    f"'{graph.fault_id}'; use direct entry or the anthropic parser"
                ),
            )

        lower = text.lower()
        extracted: dict[str, object] = {}
        notes_parts: list[str] = []

        _extract_fan_status(lower, extracted)
        _extract_airflow_and_heatsink(lower, extracted)
        _extract_load_percent(lower, extracted, notes_parts)
        _extract_ambient(lower, extracted)
        _extract_carrier(lower, extracted)
        _extract_high_load_sustained(lower, extracted)

        # A keyword hit for a field this graph does not have is reported in the
        # notes, not passed on as an unknown field or dropped without a word.
        for name in sorted(set(extracted) - graph_fields):
            notes_parts.append(f"'{name}' was mentioned but fault '{graph.fault_id}' has no such field")
            del extracted[name]

        return ParseResult(
            extracted=extracted,
            unclear_fields=[],
            rejected=[],
            notes="; ".join(notes_parts),
        )


def _extract_fan_status(lower: str, extracted: dict[str, object]) -> None:
    if "fan" not in lower:
        return
    if re.search(r"not\s+running|stopped|dead", lower):
        extracted["fan_status"] = "not_running"
    elif re.search(r"\bnoisy\b|rattl|squeak", lower):
        extracted["fan_status"] = "noisy"
    elif re.search(r"running|fine|normal|spinning", lower):
        extracted["fan_status"] = "normal"


def _extract_airflow_and_heatsink(lower: str, extracted: dict[str, object]) -> None:
    heatsink_mentioned = bool(re.search(r"heatsink|heat\s*sink", lower))
    airflow_mentioned = bool(
        re.search(r"\b(airflow|vent|vents|inlet|outlet)\b", lower)
    )

    if heatsink_mentioned:
        if re.search(r"heatsink.{0,40}clean|heat\s*sink.{0,40}clean|clean.{0,40}heatsink", lower):
            extracted["heatsink_condition"] = "clean"
        elif re.search(r"dusty|dust|dirty|clogged", lower):
            extracted["heatsink_condition"] = "dusty"

    if airflow_mentioned:
        # \bclear\b: "unclear" / "clearly" must not read as "no obstruction".
        if re.search(
            r"unobstructed|\bclear\b|no\s+obstruction|not\s+obstructed|airflow\s+is\s+fine",
            lower,
        ):
            extracted["airflow_obstruction"] = "none"
        elif re.search(r"packed|blocked|blockage|clogged|completely\s+blocked", lower):
            extracted["airflow_obstruction"] = "blocked"
        elif re.search(r"dust|partial|restricted|debris", lower):
            extracted["airflow_obstruction"] = "partial"

    # Each field is set only when the text names that part. Dusty vents say
    # nothing about the heatsink, and "there's dust everywhere" names neither.


def _extract_load_percent(
    lower: str,
    extracted: dict[str, object],
    notes_parts: list[str],
) -> None:
    # Explicit percentage near "load" / "current".
    match = re.search(
        r"(?:load|current|operating).{0,24}?(\d+(?:\.\d+)?)\s*%"
        r"|(\d+(?:\.\d+)?)\s*%.{0,24}?(?:load|current|rated)",
        lower,
    )
    if match:
        number = match.group(1) or match.group(2)
        extracted["load_percent"] = float(number) if "." in number else int(number)
        return

    # TODO(roota): "close to its rated load" / "near rated" implies high load but
    # does not state a numeric load_percent. Do not invent a percentage (e.g. 95);
    # leave the field unset until the technician gives a measured value.
    if re.search(r"close\s+to\s+(its\s+)?rated|near\s+(its\s+)?rated|around\s+rated", lower):
        notes_parts.append(
            "TODO(roota): 'close to / near rated load' mentioned but no numeric "
            "load_percent extracted — do not guess a percentage"
        )


def _extract_ambient(lower: str, extracted: dict[str, object]) -> None:
    match = re.search(
        r"(?:ambient|room|enclosure).{0,24}?(-?\d+(?:\.\d+)?)\s*°?\s*c\b"
        r"|(-?\d+(?:\.\d+)?)\s*°?\s*c\b.{0,24}?(?:ambient|room)",
        lower,
    )
    if match:
        number = match.group(1) or match.group(2)
        extracted["ambient_temp_c"] = float(number) if "." in number else int(number)


def _extract_carrier(lower: str, extracted: dict[str, object]) -> None:
    match = re.search(
        r"(?:carrier|pwm).{0,24}?(\d+(?:\.\d+)?)\s*khz"
        r"|(\d+(?:\.\d+)?)\s*khz.{0,24}?(?:carrier|pwm)",
        lower,
    )
    if match:
        number = match.group(1) or match.group(2)
        extracted["carrier_frequency_khz"] = (
            float(number) if "." in number else int(number)
        )


def _extract_high_load_sustained(lower: str, extracted: dict[str, object]) -> None:
    if not re.search(r"sustained|duty\s*cycle|long\s+period|brief\s+peak", lower):
        return
    if re.search(r"brief\s+peak|only\s+during\s+peak|not\s+sustained", lower):
        extracted["high_load_sustained"] = "no"
    elif re.search(r"sustained|long\s+period|extended", lower):
        extracted["high_load_sustained"] = "yes"

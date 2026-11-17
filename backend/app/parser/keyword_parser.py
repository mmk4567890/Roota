from __future__ import annotations

import re

from app.engine.schema import FaultGraph, UNCLEAR
from app.parser.base import ParseResult

# Fields this offline parser can fill. A graph is supported when it shares any.
KNOWN_FIELDS = frozenset(
    {
        "fan_status",
        "airflow_obstruction",
        "heatsink_condition",
        "ambient_above_derating_temp",
        "load_within_derated_capacity",
        "motor_power_vs_drive",
    }
)

# ACS580 firmware manual (fault 4290) cites 40 °C and 50 °C derating points
# that depend on frame / IP rating. Between them the answer is unclear.
_AMBIENT_YES_ABOVE_C = 50.0
_AMBIENT_NO_BELOW_C = 40.0

_HP_TO_KW = 0.746


class KeywordParser:
    """Deterministic offline observation parser.

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
        _extract_airflow(lower, extracted)
        _extract_heatsink(lower, extracted)
        _extract_ambient(lower, extracted, notes_parts)
        _extract_load_within_derated(lower, extracted)
        _extract_motor_vs_drive(lower, extracted, notes_parts)

        # A keyword hit for a field this graph does not have is reported in the
        # notes, not passed on as an unknown field or dropped without a word.
        for name in sorted(set(extracted) - graph_fields):
            notes_parts.append(
                f"'{name}' was mentioned but fault '{graph.fault_id}' has no such field"
            )
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
    if re.search(r"not\s+running|stopped|dead|\bisn'?t\s+running|is\s+not\s+running", lower):
        extracted["fan_status"] = "not_running"
    elif re.search(r"not\s+noisy|isn'?t\s+noisy|no\s+noise|not\s+rattl|not\s+squeak", lower):
        extracted["fan_status"] = "normal"
    elif re.search(r"\bnoisy\b|rattl|squeak", lower):
        extracted["fan_status"] = "noisy"
    elif re.search(r"running|fine|normal|spinning|ok\b", lower):
        extracted["fan_status"] = "normal"


def _extract_airflow(lower: str, extracted: dict[str, object]) -> None:
    airflow_mentioned = bool(
        re.search(
            r"\b(airflow|air\s*flow|air\s*path|vent|vents|inlet|outlet)\b",
            lower,
        )
    )
    if not airflow_mentioned:
        return

    # "Whether the airflow is blocked is unclear" names the field but gives no value.
    if re.search(r"\bunclear\b|\bnot\s+sure\b|\bdon'?t\s+know\b", lower):
        return

    # Prefer explicit clear / open path. Avoid matching "unclear" / "clearly"
    # via a bare "clear" substring by requiring word boundaries or other phrases.
    if re.search(
        r"unobstructed|no\s+obstruction|not\s+obstructed|not\s+blocked|"
        r"air\s*path\s+is\s+open|air\s*path\s+open|open\s+air\s*path|"
        r"airflow\s+is\s+fine|vents?\s+are\s+open|"
        r"(?<![a-z])clear(?![a-z])",
        lower,
    ):
        extracted["airflow_obstruction"] = "none"
        return

    if re.search(
        r"partly\s+blocked|partially\s+blocked|partial|restricted|"
        r"somewhat\s+blocked|a\s+bit\s+blocked",
        lower,
    ):
        extracted["airflow_obstruction"] = "partial"
    elif re.search(
        r"packed|blocked|blockage|clogged|completely\s+blocked",
        lower,
    ):
        extracted["airflow_obstruction"] = "blocked"
    elif re.search(r"\bdust\b|debris", lower):
        extracted["airflow_obstruction"] = "partial"


def _extract_heatsink(lower: str, extracted: dict[str, object]) -> None:
    heatsink_mentioned = bool(re.search(r"heatsink|heat\s*sink", lower))
    if not heatsink_mentioned:
        # "no dust" alone does not name the heatsink — leave unset.
        return

    if re.search(
        r"(heatsink|heat\s*sink).{0,40}(clean|no\s+dust|without\s+dust|not\s+dusty)"
        r"|(clean|no\s+dust|without\s+dust|not\s+dusty).{0,40}(heatsink|heat\s*sink)",
        lower,
    ):
        extracted["heatsink_condition"] = "clean"
    elif re.search(r"dusty|dust|dirty|clogged", lower):
        extracted["heatsink_condition"] = "dusty"


def _extract_ambient(
    lower: str,
    extracted: dict[str, object],
    notes_parts: list[str],
) -> None:
    # Qualitative ambient first (no number needed).
    if re.search(
        r"(ambient|room|enclosure).{0,24}(cool|cold|chilly)|"
        r"(cool|cold|chilly).{0,24}(ambient|room|enclosure)|"
        r"\broom\s+is\s+cool\b|\broom\s+is\s+cold\b",
        lower,
    ):
        extracted["ambient_above_derating_temp"] = "no"
        return
    if re.search(
        r"(ambient|room|enclosure).{0,24}(very\s+hot|hot|warm|overheating)|"
        r"(very\s+hot|hot).{0,24}(ambient|room|enclosure)|"
        r"\broom\s+is\s+hot\b",
        lower,
    ):
        extracted["ambient_above_derating_temp"] = "yes"
        return

    match = re.search(
        r"(?:ambient|room|enclosure).{0,32}?"
        r"(-?\d+(?:\.\d+)?)\s*°?\s*(?:c|celsius|centigrade)\b"
        r"|(-?\d+(?:\.\d+)?)\s*°?\s*(?:c|celsius|centigrade)\b"
        r".{0,32}?(?:ambient|room)",
        lower,
    )
    if not match:
        # Fahrenheit near ambient/room.
        f_match = re.search(
            r"(?:ambient|room|enclosure).{0,32}?"
            r"(-?\d+(?:\.\d+)?)\s*°?\s*f(?:ahrenheit)?\b"
            r"|(-?\d+(?:\.\d+)?)\s*°?\s*f(?:ahrenheit)?\b"
            r".{0,32}?(?:ambient|room)",
            lower,
        )
        if not f_match:
            return
        number = f_match.group(1) or f_match.group(2)
        temp_c = (float(number) - 32.0) * 5.0 / 9.0
    else:
        number = match.group(1) or match.group(2)
        temp_c = float(number)

    if temp_c > _AMBIENT_YES_ABOVE_C:
        extracted["ambient_above_derating_temp"] = "yes"
    elif temp_c < _AMBIENT_NO_BELOW_C:
        extracted["ambient_above_derating_temp"] = "no"
    else:
        extracted["ambient_above_derating_temp"] = UNCLEAR
        notes_parts.append(
            f"ambient {temp_c:g} °C is between 40 °C and 50 °C; the derating "
            "limit depends on frame size and IP rating (see hardware manual)"
        )


def _extract_load_within_derated(
    lower: str,
    extracted: dict[str, object],
) -> None:
    if re.search(
        r"within\s+(the\s+)?derated|"
        r"inside\s+(the\s+)?derated|"
        r"under\s+(the\s+)?derated|"
        r"below\s+(the\s+)?derated|"
        r"load\s+is\s+within|"
        r"within\s+(the\s+)?(derated\s+)?(rating|capacity)",
        lower,
    ):
        extracted["load_within_derated_capacity"] = "yes"
        return
    if re.search(
        r"full\s+load\s+in\s+this\s+heat|"
        r"running\s+at\s+full\s+load|"
        r"over\s+(the\s+)?derated|"
        r"above\s+(the\s+)?derated|"
        r"exceeds?\s+(the\s+)?derated|"
        r"outside\s+(the\s+)?derated|"
        r"beyond\s+(the\s+)?derated|"
        r"not\s+within\s+(the\s+)?derated",
        lower,
    ):
        extracted["load_within_derated_capacity"] = "no"


def _extract_motor_vs_drive(
    lower: str,
    extracted: dict[str, object],
    notes_parts: list[str],
) -> None:
    if re.search(
        r"motor\s+(matches|match(es)?|equals?)\s+(the\s+)?drive|"
        r"motor\s+and\s+drive\s+(match|are\s+matched|same)|"
        r"motor\s+(is\s+)?within\s+(the\s+)?drive|"
        r"motor\s+(power\s+)?(is\s+)?(ok|fine|sized\s+ok)|"
        r"drive\s+(is\s+)?(correctly\s+)?sized\s+for\s+(the\s+)?motor",
        lower,
    ):
        extracted["motor_power_vs_drive"] = "within"
        return
    if re.search(
        r"motor\s+(power\s+)?(exceeds?|over|oversized|too\s+big|larger\s+than)\s+(the\s+)?drive|"
        r"drive\s+(is\s+)?(too\s+small|undersized)|"
        r"motor\s+bigger\s+than\s+(the\s+)?drive",
        lower,
    ):
        extracted["motor_power_vs_drive"] = "exceeds"
        return

    motor_kw = _power_near(lower, r"motor")
    drive_kw = _power_near(lower, r"drive")
    if motor_kw is None or drive_kw is None:
        return

    if motor_kw > drive_kw:
        extracted["motor_power_vs_drive"] = "exceeds"
    elif motor_kw < drive_kw or abs(motor_kw - drive_kw) < 1e-9:
        extracted["motor_power_vs_drive"] = "within"
    else:  # pragma: no cover - float compare covered above
        notes_parts.append("could not compare motor and drive power")


def _power_near(lower: str, noun: str) -> float | None:
    """Return power in kW for ``noun is 75 kW`` / ``75 hp motor`` style phrases.

    Prefer number-adjacent forms so ``40 hp motor on a 50 hp drive`` does not
    bind the drive's 50 hp to the motor.
    """
    patterns = [
        # "75 kW motor" / "50 hp drive"
        rf"(\d+(?:\.\d+)?)\s*(kw|kilowatts?|hp|horsepower)\s+{noun}\b",
        # "motor is 75 kW" / "drive is 55 kW"
        rf"{noun}\s+is\s+(\d+(?:\.\d+)?)\s*(kw|kilowatts?|hp|horsepower)\b",
        # "motor 75kW" / "drive only 55 kW" — short gap only
        rf"{noun}\b.{{0,12}}?(\d+(?:\.\d+)?)\s*(kw|kilowatts?|hp|horsepower)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return _to_kw(float(match.group(1)), match.group(2))
    return None


def _to_kw(value: float, unit: str) -> float:
    unit_l = unit.lower()
    if unit_l in {"hp", "horsepower"}:
        return value * _HP_TO_KW
    return value

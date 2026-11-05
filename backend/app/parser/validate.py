from __future__ import annotations

from typing import Any

from app.engine.engine import validate_facts
from app.engine.schema import UNCLEAR, FaultGraph
from app.parser.base import ParseError, ParseResult, RejectedValue


def validate_parse(result: Any, graph: FaultGraph) -> ParseResult:
    """Reject invalid parser output per field; never silently drop a bad value.

    Always applied after any parser. Known-good values stay in ``extracted``.
    Ambiguous ``"unclear"`` values move to ``unclear_fields``. Unknown names,
    wrong types, and out-of-enum values become ``RejectedValue`` entries and
    never reach session facts. Structurally broken or contradictory output
    raises ``ParseError``.
    """
    if isinstance(result, ParseResult):
        raw_extracted: Any = result.extracted
        raw_unclear: Any = result.unclear_fields
        raw_rejected: Any = result.rejected
        notes = result.notes
    elif isinstance(result, dict):
        if "extracted" not in result or "unclear_fields" not in result:
            raise ParseError("parser output is missing required keys")
        if "rejected" not in result or "notes" not in result:
            raise ParseError("parser output is missing required keys")
        raw_extracted = result["extracted"]
        raw_unclear = result["unclear_fields"]
        raw_rejected = result["rejected"]
        notes = result["notes"]
    else:
        raise ParseError(
            f"parser output must be a ParseResult or dict, got {type(result).__name__}"
        )

    if not isinstance(raw_extracted, dict):
        raise ParseError(
            f"extracted must be a dict, got {type(raw_extracted).__name__}"
        )
    if not isinstance(raw_unclear, list):
        raise ParseError(
            f"unclear_fields must be a list, got {type(raw_unclear).__name__}"
        )
    if not isinstance(notes, str):
        raise ParseError(f"notes must be a string, got {type(notes).__name__}")

    field_by_name = {field.name: field for field in graph.fields}
    rejected: list[RejectedValue] = _copy_existing_rejected(raw_rejected)
    extracted: dict[str, Any] = {}
    unclear: list[str] = []
    unclear_seen: set[str] = set()

    for name in raw_unclear:
        if not isinstance(name, str):
            raise ParseError(
                f"unclear_fields entries must be strings, got {type(name).__name__}"
            )
        if name not in field_by_name:
            rejected.append(
                RejectedValue(
                    field=name,
                    value=None,
                    reason=f"unknown field '{name}'",
                )
            )
            continue
        if name not in unclear_seen:
            unclear.append(name)
            unclear_seen.add(name)

    for name, value in raw_extracted.items():
        if not isinstance(name, str):
            raise ParseError(
                f"extracted keys must be strings, got {type(name).__name__}"
            )
        if name not in field_by_name:
            rejected.append(
                RejectedValue(
                    field=name,
                    value=value,
                    reason=f"unknown field '{name}'",
                )
            )
            continue

        if value == UNCLEAR:
            if name not in unclear_seen:
                unclear.append(name)
                unclear_seen.add(name)
            continue

        try:
            validate_facts(graph, {name: value})
        except ValueError as error:
            rejected.append(
                RejectedValue(field=name, value=value, reason=str(error))
            )
            continue

        extracted[name] = value

    overlap = sorted(set(extracted) & set(unclear))
    if overlap:
        names = ", ".join(overlap)
        raise ParseError(
            f"contradictory parser output: field(s) in both extracted and "
            f"unclear_fields: {names}"
        )

    return ParseResult(
        extracted=extracted,
        unclear_fields=unclear,
        rejected=rejected,
        notes=notes,
    )


def _copy_existing_rejected(raw_rejected: Any) -> list[RejectedValue]:
    if not isinstance(raw_rejected, list):
        raise ParseError(
            f"rejected must be a list, got {type(raw_rejected).__name__}"
        )
    copied: list[RejectedValue] = []
    for item in raw_rejected:
        if isinstance(item, RejectedValue):
            copied.append(item)
        elif isinstance(item, dict):
            try:
                copied.append(RejectedValue.model_validate(item))
            except Exception as error:
                raise ParseError(
                    f"rejected entry is invalid: {error}"
                ) from error
        else:
            raise ParseError(
                f"rejected entry must be RejectedValue or dict, "
                f"got {type(item).__name__}"
            )
    return copied

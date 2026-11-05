#!/usr/bin/env python3
"""Run parser_eval/cases.jsonl against a chosen parser and print accuracy.

This script is the only place that may call the real Anthropic API, and only
when run by hand with ROOTA_PARSER=anthropic. Do not import it from pytest.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.parser.anthropic_parser import AnthropicParser
from app.parser.fake import KeywordParser
from app.parser.base import ParseError
from app.parser.validate import validate_parse

DEFAULT_CASES = BACKEND_ROOT / "tests" / "parser_eval" / "cases.jsonl"


def _load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                cases.append(json.loads(stripped))
            except json.JSONDecodeError as error:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {error}") from error
    return cases


def _check_fields(graph, check_id: str | None) -> list[str]:
    if check_id is None:
        return []
    for check in graph.checks:
        if check.id == check_id:
            return list(check.collects)
    raise SystemExit(f"Unknown check_id '{check_id}' in cases")


def _values_match(actual: object, expected: object) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(actual) == float(expected)
    return actual == expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--parser",
        choices=("keyword", "anthropic"),
        default="keyword",
        help="Which parser to evaluate (default: keyword)",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES,
        help=f"JSONL cases file (default: {DEFAULT_CASES})",
    )
    parser.add_argument(
        "--fault-id",
        default="overtemperature",
        help="Fault graph id to evaluate against",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Evaluate only the first N cases (useful for anthropic cost control)",
    )
    args = parser.parse_args()

    graphs = load_graphs(DEFAULT_GRAPHS_DIR)
    if args.fault_id not in graphs:
        raise SystemExit(f"Unknown fault_id '{args.fault_id}'")
    graph = graphs[args.fault_id]

    if args.parser == "keyword":
        observation_parser = KeywordParser()
    else:
        observation_parser = AnthropicParser()

    cases = _load_cases(args.cases)
    if not cases:
        raise SystemExit(f"No cases found in {args.cases}")
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit must be >= 1")
        cases = cases[: args.limit]

    field_hits = 0
    field_total = 0
    case_hits = 0
    api_calls = 0
    failures: list[str] = []

    for case in cases:
        case_id = case.get("id", "<missing id>")
        text = case["text"]
        expected: dict = case.get("expected") or {}
        absent: list[str] = case.get("absent") or []
        # The case's own check_id, never the expected keys: passing those would
        # tell the parser which fields the answer contains.
        expected_fields = _check_fields(graph, case.get("check_id"))

        try:
            api_calls += 1
            parsed = validate_parse(
                observation_parser.parse(text, graph, expected_fields), graph
            )
        except ParseError as error:
            field_total += len(expected) + len(absent)
            failures.append(f"{case_id}: parser error: {error}")
            continue

        case_ok = True
        for field_name, expected_value in expected.items():
            field_total += 1
            actual = parsed.extracted.get(field_name)
            if field_name in parsed.extracted and _values_match(actual, expected_value):
                field_hits += 1
            else:
                case_ok = False
                failures.append(
                    f"{case_id}: expected {field_name}={expected_value!r}, "
                    f"got {actual!r} (extracted={parsed.extracted})"
                )

        for field_name in absent:
            field_total += 1
            if field_name in parsed.extracted:
                case_ok = False
                failures.append(
                    f"{case_id}: expected {field_name} absent, "
                    f"got {parsed.extracted[field_name]!r}"
                )
            else:
                field_hits += 1

        if case_ok:
            case_hits += 1

    case_accuracy = case_hits / len(cases)
    field_accuracy = field_hits / field_total if field_total else 0.0

    print(f"parser={args.parser} cases={len(cases)} fault_id={args.fault_id}")
    print(f"api_calls={api_calls}")
    print(f"case_accuracy={case_accuracy:.1%} ({case_hits}/{len(cases)})")
    print(f"field_accuracy={field_accuracy:.1%} ({field_hits}/{field_total})")
    if failures:
        print("failures:")
        for line in failures:
            print(f"  - {line}")
    return 0 if case_hits == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())

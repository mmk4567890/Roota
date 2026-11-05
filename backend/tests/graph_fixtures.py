"""Fault graphs used only by tests.

``tests/fixtures/graphs/overtemperature.json`` is the generic placeholder graph
Roota was built with. Its thresholds and citations are invented, so it never
ships; it stays here because engine, parser and session tests exercise its
numeric thresholds, promotion and boundaries. The shipped graphs live in
``app/graphs/data/`` and are tested in ``test_shipped_graphs.py``.
"""

from __future__ import annotations

from pathlib import Path

from app.engine.schema import FaultGraph
from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs

TEST_GRAPHS_DIR = Path(__file__).resolve().parent / "fixtures" / "graphs"


def all_graphs() -> dict[str, FaultGraph]:
    """Shipped graphs plus the test-only ones, as the test API client serves them."""
    shipped = load_graphs(DEFAULT_GRAPHS_DIR)
    fixtures = load_graphs(TEST_GRAPHS_DIR)
    overlap = set(shipped) & set(fixtures)
    if overlap:
        raise ValueError(f"test graph ids collide with shipped graphs: {sorted(overlap)}")
    return {**shipped, **fixtures}

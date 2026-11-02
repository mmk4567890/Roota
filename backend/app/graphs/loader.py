from __future__ import annotations

import json
from pathlib import Path

from app.engine.schema import FaultGraph

DEFAULT_GRAPHS_DIR = Path(__file__).resolve().parent / "data"

_cache: dict[str, FaultGraph] | None = None
_cache_dir: Path | None = None


def load_graphs(directory: Path | str | None = None) -> dict[str, FaultGraph]:
    """Load and validate every ``*.json`` fault graph from ``directory``."""
    global _cache, _cache_dir

    graphs_dir = Path(directory) if directory is not None else DEFAULT_GRAPHS_DIR
    if not graphs_dir.is_dir():
        raise FileNotFoundError(f"Graphs directory not found: {graphs_dir}")

    loaded: dict[str, FaultGraph] = {}
    for path in sorted(graphs_dir.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        graph = FaultGraph.model_validate(payload)
        if graph.fault_id in loaded:
            raise ValueError(
                f"duplicate fault_id '{graph.fault_id}' from {path.name}"
            )
        loaded[graph.fault_id] = graph

    _cache = loaded
    _cache_dir = graphs_dir
    return loaded


def get_graph(fault_id: str) -> FaultGraph | None:
    """Return a cached graph by id, or None if missing / not yet loaded."""
    if _cache is None:
        return None
    return _cache.get(fault_id)


def get_cached_graphs() -> dict[str, FaultGraph]:
    """Return the startup cache, or an empty dict if not loaded yet."""
    return _cache if _cache is not None else {}


def clear_graph_cache() -> None:
    """Drop the in-process cache (intended for tests)."""
    global _cache, _cache_dir
    _cache = None
    _cache_dir = None

from fastapi import APIRouter, Depends

from app.engine.schema import FaultGraph
from app.graphs.loader import get_cached_graphs

router = APIRouter(tags=["faults"])


def get_graphs() -> dict[str, FaultGraph]:
    """Return loaded fault graphs. Overridable in tests."""
    return get_cached_graphs()


@router.get("/faults")
def list_faults(
    graphs: dict[str, FaultGraph] = Depends(get_graphs),
) -> list[dict[str, object]]:
    return [
        {
            "fault_id": graph.fault_id,
            "display_name": graph.display_name,
            "fault_codes": graph.fault_codes,
            "description": graph.description,
        }
        for graph in graphs.values()
    ]

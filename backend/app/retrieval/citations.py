from __future__ import annotations

from dataclasses import dataclass

from app.engine.schema import FaultGraph, Source
from app.retrieval.store import TBD_MANUAL, DocsRegistry


@dataclass(frozen=True)
class CitationIssue:
    kind: str  # "missing_doc" | "missing_page" | "empty_page"
    fault_id: str
    location: str
    doc_id: str
    page: int | None
    detail: str


def iter_sources(graph: FaultGraph) -> list[tuple[str, Source]]:
    found: list[tuple[str, Source]] = []
    for check in graph.checks:
        found.append((f"check:{check.id}", check.source))
    for cause in graph.causes:
        found.append((f"cause:{cause.id}.action_source", cause.action_source))
    return found


def check_citations(
    graphs: dict[str, FaultGraph],
    registry: DocsRegistry,
) -> list[CitationIssue]:
    """Return citation problems for graph sources against the docs registry."""
    issues: list[CitationIssue] = []
    for fault_id, graph in sorted(graphs.items()):
        for location, source in iter_sources(graph):
            if source.doc_id == TBD_MANUAL:
                continue
            record = registry.get_doc(source.doc_id)
            if record is None:
                issues.append(
                    CitationIssue(
                        kind="missing_doc",
                        fault_id=fault_id,
                        location=location,
                        doc_id=source.doc_id,
                        page=source.page,
                        detail=f"doc_id '{source.doc_id}' is not in the docs registry",
                    )
                )
                continue
            if source.page is None:
                issues.append(
                    CitationIssue(
                        kind="missing_page",
                        fault_id=fault_id,
                        location=location,
                        doc_id=source.doc_id,
                        page=None,
                        detail=(
                            f"doc_id '{source.doc_id}' is ingested "
                            f"({record.page_count} pages) but source.page is null"
                        ),
                    )
                )
            elif source.page < 1 or source.page > record.page_count:
                issues.append(
                    CitationIssue(
                        kind="missing_page",
                        fault_id=fault_id,
                        location=location,
                        doc_id=source.doc_id,
                        page=source.page,
                        detail=(
                            f"page {source.page} is outside 1..{record.page_count} "
                            f"for doc_id '{source.doc_id}'"
                        ),
                    )
                )
            elif source.page in record.empty_pages:
                # The page exists but has no extractable text (scanned), so the
                # technician would get no cited passage for this check.
                issues.append(
                    CitationIssue(
                        kind="empty_page",
                        fault_id=fault_id,
                        location=location,
                        doc_id=source.doc_id,
                        page=source.page,
                        detail=(
                            f"page {source.page} of doc_id '{source.doc_id}' has no "
                            f"extractable text, so no cited passage can be shown"
                        ),
                    )
                )
    return issues

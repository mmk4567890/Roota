from __future__ import annotations

import re

from app.engine.engine import Evidence
from app.engine.schema import Source
from app.retrieval.ingest import ENTRY_START_RE
from app.retrieval.passage import reflow_passage
from app.retrieval.store import TBD_MANUAL, ManualStore, StoredChunk

def get_evidence(
    source: Source,
    query: str,
    k: int = 3,
    *,
    store: ManualStore,
) -> list[Evidence]:
    """Return cited chunks first, then related semantic matches in the same doc.

    A cited page holds several chunks, often other faults' entries (PDF page
    554 of the ACS580 manual opens with 3210 DC link overvoltage). All of the
    page's chunks stay cited, ordered by relevance to ``query``.

    Evidence ``text`` is verbatim from the stored manual — never summarised.
    Unknown / placeholder docs return an empty list without raising.
    """
    if source.doc_id == TBD_MANUAL:
        return []

    manual_store = store
    if not manual_store.has_doc(source.doc_id):
        return []

    cited_chunks: list[StoredChunk] = []
    if source.page is not None:
        cited_chunks = _most_relevant_first(
            manual_store.get_chunks_for_page(source.doc_id, source.page),
            source,
            query,
            manual_store,
        )

    cited_ids = {chunk.chunk_id for chunk in cited_chunks}
    related_chunks = manual_store.search(
        query,
        doc_id=source.doc_id,
        k=k,
        exclude_ids=cited_ids,
    )

    evidence: list[Evidence] = [
        Evidence(
            doc_id=chunk.doc_id,
            title=chunk.title,
            page=chunk.page,
            section=chunk.section,
            text=reflow_passage(chunk.text),
            kind="cited",
        )
        for chunk in cited_chunks
    ]
    evidence.extend(
        Evidence(
            doc_id=chunk.doc_id,
            title=chunk.title,
            page=chunk.page,
            section=chunk.section,
            text=reflow_passage(chunk.text),
            kind="related",
        )
        for chunk in related_chunks
    )
    return evidence


def _most_relevant_first(
    chunks: list[StoredChunk], source: Source, query: str, store: ManualStore
) -> list[StoredChunk]:
    if len(chunks) < 2:
        return chunks
    ranked = store.search(query, doc_id=source.doc_id, page=source.page, k=len(chunks))
    rank = {chunk.chunk_id: position for position, chunk in enumerate(ranked)}
    missing = [chunk.chunk_id for chunk in chunks if chunk.chunk_id not in rank]
    if missing:
        # search over the same page must return every one of its chunks.
        raise RuntimeError(f"relevance ranking lost cited chunks: {missing}")
    # The citation names its entry ("Fault tracing: 4210 IGBT overtemperature"):
    # the chunk that opens with that entry's code leads. Meaning-based ranking
    # alone put neighbouring cooling entries (4110) ahead of the cited 4210.
    cited_codes = set(re.findall(r"\b[0-9A-F]{4}\b", source.section))
    return sorted(
        chunks,
        key=lambda chunk: (_entry_code(chunk.text) not in cited_codes, rank[chunk.chunk_id]),
    )


def _entry_code(text: str) -> str | None:
    match = ENTRY_START_RE.match(text.lstrip())
    return match.group(0)[:4] if match else None

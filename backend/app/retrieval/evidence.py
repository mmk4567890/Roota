from __future__ import annotations

from app.engine.engine import Evidence
from app.engine.schema import Source
from app.retrieval.store import TBD_MANUAL, ManualStore, StoredChunk

def get_evidence(
    source: Source,
    query: str,
    k: int = 3,
    *,
    store: ManualStore,
) -> list[Evidence]:
    """Return cited chunks first, then related semantic matches in the same doc.

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
        cited_chunks = manual_store.get_chunks_for_page(source.doc_id, source.page)

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
            text=chunk.text,
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
            text=chunk.text,
            kind="related",
        )
        for chunk in related_chunks
    )
    return evidence

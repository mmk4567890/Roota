"""Cited evidence: every chunk of the cited page, most relevant first."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.engine.schema import Source
from app.retrieval.embeddings import FakeEmbeddingFunction
from app.retrieval.evidence import get_evidence
from app.retrieval.store import ManualStore, StoredChunk


def _chunk(chunk_id: str, page: int, text: str) -> StoredChunk:
    return StoredChunk(chunk_id=chunk_id, doc_id="m", title="M", page=page, section="", text=text)


class RankingStore:
    """Store stub: page 7 holds an overvoltage entry, then the fan entry."""

    def __init__(self, ranked_ids: list[str]) -> None:
        self.page_chunks = [
            _chunk("m::p7::c0", 7, "3210 DC link overvoltage. Check the supply."),
            _chunk("m::p7::c1", 7, "4210 IGBT overtemperature. Check air flow and fan operation."),
        ]
        self.ranked_ids = ranked_ids
        self.searches: list[dict[str, object]] = []

    def has_doc(self, doc_id: str) -> bool:
        return doc_id == "m"

    def get_chunks_for_page(self, doc_id: str, page: int) -> list[StoredChunk]:
        return list(self.page_chunks)

    def search(self, query: str, *, doc_id=None, page=None, k=5, exclude_ids=None):
        self.searches.append({"page": page, "k": k, "exclude": exclude_ids})
        if page is not None:
            by_id = {chunk.chunk_id: chunk for chunk in self.page_chunks}
            return [by_id[chunk_id] for chunk_id in self.ranked_ids]
        return []


def test_most_relevant_cited_chunk_comes_first() -> None:
    store = RankingStore(ranked_ids=["m::p7::c1", "m::p7::c0"])

    evidence = get_evidence(Source(doc_id="m", section="", page=7), "cooling fan", store=store)

    assert [item.text[:4] for item in evidence] == ["4210", "3210"]
    assert all(item.kind == "cited" for item in evidence)
    # The ranking search is limited to the cited page and asks for all of it.
    assert store.searches[0] == {"page": 7, "k": 2, "exclude": None}


def test_chunk_named_by_the_citation_leads_over_relevance() -> None:
    # Meaning-based ranking prefers the overvoltage chunk here, but the
    # citation names 4210, so the 4210 entry leads.
    store = RankingStore(ranked_ids=["m::p7::c0", "m::p7::c1"])
    source = Source(doc_id="m", section="Fault tracing: 4210 IGBT overtemperature", page=7)

    evidence = get_evidence(source, "cooling fan", store=store)

    assert [item.text[:4] for item in evidence] == ["4210", "3210"]


def test_code_inside_other_words_is_not_a_cited_code() -> None:
    # "p. 3210x" is not the entry code 3210: word boundaries apply.
    store = RankingStore(ranked_ids=["m::p7::c1", "m::p7::c0"])
    source = Source(doc_id="m", section="Fault tracing: see p. 3210x", page=7)

    evidence = get_evidence(source, "cooling fan", store=store)

    assert [item.text[:4] for item in evidence] == ["4210", "3210"]


def test_ranking_that_loses_a_cited_chunk_is_an_error() -> None:
    store = RankingStore(ranked_ids=["m::p7::c1"])

    with pytest.raises(RuntimeError, match="lost cited chunks"):
        get_evidence(Source(doc_id="m", section="", page=7), "cooling fan", store=store)


def test_single_chunk_page_needs_no_ranking() -> None:
    store = RankingStore(ranked_ids=[])
    store.page_chunks = store.page_chunks[:1]

    evidence = get_evidence(Source(doc_id="m", section="", page=7), "cooling fan", store=store)

    assert len(evidence) == 1
    assert all(search["page"] is None for search in store.searches)


def test_page_filtered_search_stays_on_the_page(tmp_path: Path) -> None:
    store = ManualStore(
        chroma_dir=tmp_path / "c",
        docs_db_path=tmp_path / "d.db",
        embedding_function=FakeEmbeddingFunction(),
    )
    store.replace_chunks(
        doc_id="m",
        title="M",
        filename="m.pdf",
        page_count=2,
        empty_pages=[],
        chunks=[
            _chunk("m::p1::c0", 1, "cooling fan airflow"),
            _chunk("m::p2::c0", 2, "cooling fan airflow heatsink"),
            _chunk("m::p2::c1", 2, "supply voltage"),
        ],
    )

    hits = store.search("cooling fan", doc_id="m", page=2, k=5)

    assert sorted(hit.chunk_id for hit in hits) == ["m::p2::c0", "m::p2::c1"]


def test_page_filter_requires_doc_id(tmp_path: Path) -> None:
    store = ManualStore(
        chroma_dir=tmp_path / "c",
        docs_db_path=tmp_path / "d.db",
        embedding_function=FakeEmbeddingFunction(),
    )
    with pytest.raises(ValueError, match="page filter requires doc_id"):
        store.search("fan", page=2)


# --- chunks start at fault-table entries ---

FAULT_TABLE_PAGE = """556   Fault tracing
3210 DC link overvoltage Excessive intermediate circuit
DC voltage.
3385 Autophasing Autophasing routine has failed.
0002 Motor is rotating during
autophasing.
4210 IGBT overtemperature Estimated drive IGBT
temperature is excessive.
Check air flow and fan operation.
"""


def test_chunks_start_at_fault_entries() -> None:
    from app.retrieval.ingest import chunk_page_text

    chunks = chunk_page_text(FAULT_TABLE_PAGE, page=554, doc_id="m", title="M")

    assert [chunk.text.split("\n")[0].strip() for chunk in chunks] == [
        "556   Fault tracing",
        "3210 DC link overvoltage Excessive intermediate circuit",
        "3385 Autophasing Autophasing routine has failed.",
        "4210 IGBT overtemperature Estimated drive IGBT",
    ]
    # An auxiliary code (000x) stays with its parent entry.
    assert "0002 Motor is rotating" in chunks[2].text
    # Nothing is lost or duplicated without overlap inside short entries.
    assert "".join(chunk.text for chunk in chunks) == FAULT_TABLE_PAGE
    assert [chunk.chunk_id for chunk in chunks] == [f"m::p554::c{i}" for i in range(4)]


def test_long_entry_is_still_windowed_within_the_entry() -> None:
    from app.retrieval.ingest import chunk_page_text

    text = "4210 IGBT overtemperature " + "check air flow " * 120 + "\n4290 Cooling Drive module.\n"
    chunks = chunk_page_text(text, page=1, doc_id="m", title="M", chunk_size=800, overlap=150)

    assert all(len(chunk.text) <= 800 for chunk in chunks)
    assert chunks[-1].text.startswith("4290 Cooling")
    assert not any("4290" in chunk.text for chunk in chunks[:-1])


def test_text_without_entries_is_chunked_as_before() -> None:
    from app.retrieval.ingest import chunk_page_text

    text = "plain manual prose " * 100
    chunks = chunk_page_text(text, page=1, doc_id="m", title="M", chunk_size=800, overlap=150)

    assert [len(chunk.text) for chunk in chunks][:2] == [800, 800]
    assert chunks[1].text.startswith(text[650:660])

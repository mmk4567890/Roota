"""Regression tests for the Prompt 6 review fixes."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.engine.schema import Source
from app.graphs.loader import load_graphs
from tests.graph_fixtures import TEST_GRAPHS_DIR
from app.retrieval.citations import check_citations
from app.retrieval.embeddings import FakeEmbeddingFunction
from app.retrieval.evidence import get_evidence
from app.retrieval.ingest import detect_section, ingest_pdf
from app.retrieval.store import DocsRegistry, ManualStore
from app.routers import docs
from tests.test_retrieval import _make_pdf


@pytest.fixture
def store(tmp_path: Path) -> ManualStore:
    return ManualStore(
        chroma_dir=tmp_path / "chroma",
        docs_db_path=tmp_path / "docs.db",
        embedding_function=FakeEmbeddingFunction(),
    )


@pytest.fixture
def blank_page_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "scan.pdf"
    path.write_bytes(_make_pdf(["7.3 Fault Codes\nCooling fan inspection text.", ""]))
    return path


# --- scanned pages are recorded, never stored as blank passages ---


def test_search_never_returns_blank_passage_for_scanned_page(
    store: ManualStore, blank_page_pdf: Path
) -> None:
    ingest_pdf(blank_page_pdf, doc_id="scan", title="Scan", store=store)

    hits = store.search("anything", doc_id="scan", k=5)

    assert [hit.page for hit in hits] == [1]
    assert all(hit.text.strip() for hit in hits)


def test_evidence_for_text_page_has_no_blank_related_passage(
    store: ManualStore, blank_page_pdf: Path
) -> None:
    ingest_pdf(blank_page_pdf, doc_id="scan", title="Scan", store=store)

    evidence = get_evidence(
        Source(doc_id="scan", section="7.3 Fault Codes", page=1), "fan", store=store
    )

    assert [(item.kind, item.page) for item in evidence] == [("cited", 1)]


def test_docs_api_lists_empty_pages(
    client: TestClient, store: ManualStore, blank_page_pdf: Path
) -> None:
    ingest_pdf(blank_page_pdf, doc_id="scan", title="Scan", store=store)
    client.app.dependency_overrides[docs.get_manual_store] = lambda: store

    body = client.get("/docs").json()

    assert body == [
        {
            "doc_id": "scan",
            "title": "Scan",
            "filename": "scan.pdf",
            "page_count": 2,
            "empty_pages": [2],
        }
    ]


def test_registry_created_before_empty_pages_column_still_opens(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE docs (doc_id TEXT PRIMARY KEY, title TEXT NOT NULL, "
            "filename TEXT NOT NULL, page_count INTEGER NOT NULL)"
        )
        connection.execute("INSERT INTO docs VALUES ('old', 'Old', 'old.pdf', 3)")
        connection.commit()
    finally:
        connection.close()

    record = DocsRegistry(path).get_doc("old")

    assert record is not None
    assert record.page_count == 3
    assert record.empty_pages == ()


# --- section headings ---


@pytest.mark.parametrize(
    "line", ["1.5 kW rated output", "2.2 Nm on terminals", "0.75 mm2 cable", "3.10 s ramp"]
)
def test_spec_values_are_not_section_headings(line: str) -> None:
    assert detect_section(f"Ratings\n{line}\nmore text", 200) == ""


@pytest.mark.parametrize("line", ["7.3 Fault Codes", "4.1.2 Cooling fan", "3.10 IGBT overheating"])
def test_numbered_headings_still_detected(line: str) -> None:
    assert detect_section(f"{line}\nbody text", 200) == line


# --- a failed re-ingest never leaves the registry claiming deleted chunks ---


class _FailingEmbedding(FakeEmbeddingFunction):
    def __call__(self, input: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding failed")


def test_failed_reingest_marks_doc_not_ingested(
    tmp_path: Path, store: ManualStore, blank_page_pdf: Path
) -> None:
    ingest_pdf(blank_page_pdf, doc_id="scan", title="Scan", store=store)
    assert store.count_chunks("scan") == 1

    store._collection._embedding_function = _FailingEmbedding()
    with pytest.raises(Exception, match="embedding failed"):
        ingest_pdf(blank_page_pdf, doc_id="scan", title="Scan v2", store=store)

    assert store.count_chunks("scan") == 0
    assert store.has_doc("scan") is False
    assert get_evidence(Source(doc_id="scan", section="", page=1), "fan", store=store) == []
    graphs = load_graphs(TEST_GRAPHS_DIR)
    graph = graphs["overtemperature"]
    cited = graph.checks[0].model_copy(
        update={"source": Source(doc_id="scan", section="", page=1)}
    )
    patched = {"overtemperature": graph.model_copy(update={"checks": [cited, *graph.checks[1:]]})}
    assert [issue.kind for issue in check_citations(patched, store.registry)] == ["missing_doc"]


# --- citation check ---


def test_citation_to_scanned_page_is_reported(
    store: ManualStore, blank_page_pdf: Path
) -> None:
    ingest_pdf(blank_page_pdf, doc_id="scan", title="Scan", store=store)
    graphs = load_graphs(TEST_GRAPHS_DIR)
    graph = graphs["overtemperature"]
    cited = graph.checks[0].model_copy(
        update={"source": Source(doc_id="scan", section="", page=2)}
    )
    patched = {"overtemperature": graph.model_copy(update={"checks": [cited, *graph.checks[1:]]})}

    issues = check_citations(patched, store.registry)

    assert [(issue.kind, issue.page) for issue in issues] == [("empty_page", 2)]


class _OtherEmbedding(FakeEmbeddingFunction):
    @staticmethod
    def name() -> str:
        return "other_embedding"


def test_check_citations_script_ignores_collection_embedding(
    tmp_path: Path, blank_page_pdf: Path
) -> None:
    # Real manuals are ingested with Chroma's default embedding. Chroma refuses
    # to reopen that collection with any other embedding, so the script must
    # read only the registry.
    real_store = ManualStore(
        chroma_dir=tmp_path / "real-chroma",
        docs_db_path=tmp_path / "real-docs.db",
        embedding_function=_OtherEmbedding(),
    )
    ingest_pdf(blank_page_pdf, doc_id="scan", title="Scan", store=real_store)
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_citations.py"
    spec = importlib.util.spec_from_file_location("check_citations_review", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # The test graphs cite TBD_MANUAL only, so a clean run exits 0.
    assert (
        module.main(
            [
                "--docs-db",
                str(tmp_path / "real-docs.db"),
                "--graphs-dir",
                str(TEST_GRAPHS_DIR),
            ]
        )
        == 0
    )


# --- dependencies: no process-wide fallback store ---


def test_unconfigured_manual_store_raises() -> None:
    bare = FastAPI(docs_url=None)  # FastAPI's own Swagger page also lives at /docs
    bare.include_router(docs.router)

    with pytest.raises(RuntimeError, match="Manual store was not configured"):
        TestClient(bare).get("/docs")


def test_get_evidence_requires_a_store() -> None:
    with pytest.raises(TypeError):
        get_evidence(Source(doc_id="scan", section="", page=1), "fan")  # type: ignore[call-arg]


def test_search_query_length_limited(client: TestClient) -> None:
    response = client.get("/docs/search", params={"q": "x" * 501})
    assert response.status_code == 422

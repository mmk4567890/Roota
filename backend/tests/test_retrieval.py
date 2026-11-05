from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.engine.schema import Source
from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.main import app
from app.retrieval.citations import check_citations
from app.retrieval.embeddings import FakeEmbeddingFunction
from app.retrieval.evidence import get_evidence
from app.retrieval.ingest import (
    build_chunks,
    chunk_page_text,
    extract_pages,
    ingest_pdf,
)
from app.retrieval.store import ManualStore, validate_doc_id
from app.routers import docs
from app.graphs import loader as graph_loader


def _make_pdf(pages: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    for text in pages:
        if text:
            y = 720
            for line in text.split("\n"):
                pdf.drawString(72, y, line[:110])
                y -= 14
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@pytest.fixture
def fake_store(tmp_path: Path) -> ManualStore:
    return ManualStore(
        chroma_dir=tmp_path / "chroma",
        docs_db_path=tmp_path / "docs.db",
        embedding_function=FakeEmbeddingFunction(),
    )


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    page1 = (
        "7.3 Fault Codes\n"
        "Cooling fan inspection: observe the drive cooling fan while powered. "
        "Replace the fan assembly if it is not running or is noisy. "
        + ("fan cooling airflow " * 40)
    )
    page2 = (
        "7.4 Load and duty cycle\n"
        "Measure output current as a percentage of rated current. "
        "Sustained high load increases heatsink temperature. "
        + ("load current rated duty " * 40)
    )
    path = tmp_path / "manual.pdf"
    path.write_bytes(_make_pdf([page1, page2]))
    return path


def test_validate_doc_id_rejects_bad_values() -> None:
    with pytest.raises(ValueError, match="invalid doc_id"):
        validate_doc_id("TBD_MANUAL")
    with pytest.raises(ValueError, match="invalid doc_id"):
        validate_doc_id("Bad Id")
    with pytest.raises(ValueError, match="invalid doc_id"):
        validate_doc_id("")
    with pytest.raises(ValueError, match="invalid doc_id"):
        validate_doc_id("x" * 65)
    assert validate_doc_id("ac_drive-manual_01") == "ac_drive-manual_01"


def test_page_numbers_preserved_and_chunks_never_span_pages(
    fake_store: ManualStore, sample_pdf: Path
) -> None:
    pages = extract_pages(sample_pdf)
    assert len(pages) == 2
    assert pages[0].page == 1
    assert pages[1].page == 2
    assert "Cooling fan" in pages[0].text
    assert "rated current" in pages[1].text

    chunks = build_chunks(pages, doc_id="demo_manual", title="Demo Manual")
    assert chunks
    page_text = {page.page: page.text for page in pages}
    for chunk in chunks:
        assert chunk.page in (1, 2)
        if chunk.text:
            assert chunk.text in page_text[chunk.page]
        # Unique markers must stay on their page.
        if "Cooling fan inspection" in chunk.text:
            assert chunk.page == 1
            assert "Measure output current" not in chunk.text
        if "Measure output current" in chunk.text:
            assert chunk.page == 2
            assert "Cooling fan inspection" not in chunk.text

    result = ingest_pdf(
        sample_pdf,
        doc_id="demo_manual",
        title="Demo Manual",
        store=fake_store,
    )
    assert result.page_count == 2
    assert result.chunk_count == len(chunks)
    assert result.empty_pages == []


def test_empty_page_recorded_and_cli_reports(
    fake_store: ManualStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "blankish.pdf"
    path.write_bytes(_make_pdf(["Page one has text about the cooling fan.", ""]))
    result = ingest_pdf(
        path,
        doc_id="blank_manual",
        title="Blankish",
        store=fake_store,
    )
    assert result.page_count == 2
    assert result.empty_pages == [2]
    # Recorded in the registry, not as a blank chunk search could return.
    assert fake_store.get_chunks_for_page("blank_manual", 2) == []
    assert fake_store.get_doc("blank_manual").empty_pages == (2,)

    monkeypatch.setattr(
        "app.retrieval.ingest.ManualStore",
        lambda: fake_store,
    )
    from app.retrieval.ingest import main as ingest_main

    assert ingest_main([str(path), "--doc-id", "blank_manual", "--title", "Blankish"]) == 0
    captured = capsys.readouterr()
    assert "no extractable text" in captured.out
    assert "2" in captured.out


def test_reingest_same_doc_id_is_idempotent(
    fake_store: ManualStore, sample_pdf: Path
) -> None:
    first = ingest_pdf(
        sample_pdf, doc_id="demo_manual", title="Demo", store=fake_store
    )
    second = ingest_pdf(
        sample_pdf, doc_id="demo_manual", title="Demo", store=fake_store
    )
    assert first.chunk_count == second.chunk_count
    assert fake_store.count_chunks("demo_manual") == first.chunk_count


def test_section_heading_detected() -> None:
    text = "intro line\n7.3 Fault Codes\nbody about fans\n"
    chunks = chunk_page_text(
        text, page=1, doc_id="x", title="t", chunk_size=800, overlap=150
    )
    assert chunks[0].section == "7.3 Fault Codes"


def test_cited_evidence_comes_first(
    fake_store: ManualStore, sample_pdf: Path
) -> None:
    ingest_pdf(sample_pdf, doc_id="demo_manual", title="Demo Manual", store=fake_store)
    source = Source(doc_id="demo_manual", section="7.3", page=1)
    evidence = get_evidence(
        source,
        query="measure output current rated load duty cycle",
        k=3,
        store=fake_store,
    )
    assert evidence
    assert evidence[0].kind == "cited"
    assert evidence[0].page == 1
    kinds = [item.kind for item in evidence]
    if "related" in kinds:
        last_cited = max(i for i, kind in enumerate(kinds) if kind == "cited")
        first_related = min(i for i, kind in enumerate(kinds) if kind == "related")
        assert last_cited < first_related

    cited_ids_texts = {(item.page, item.text) for item in evidence if item.kind == "cited"}
    for item in evidence:
        if item.kind == "related":
            assert (item.page, item.text) not in cited_ids_texts


def test_unknown_and_tbd_doc_return_empty(fake_store: ManualStore) -> None:
    assert (
        get_evidence(
            Source(doc_id="TBD_MANUAL", section="x", page=1),
            "fan",
            store=fake_store,
        )
        == []
    )
    assert (
        get_evidence(
            Source(doc_id="missing_doc", section="x", page=1),
            "fan",
            store=fake_store,
        )
        == []
    )


def test_evidence_text_is_verbatim(
    fake_store: ManualStore, sample_pdf: Path
) -> None:
    ingest_pdf(sample_pdf, doc_id="demo_manual", title="Demo Manual", store=fake_store)
    pages = extract_pages(sample_pdf)
    evidence = get_evidence(
        Source(doc_id="demo_manual", section="7.3", page=1),
        "cooling fan",
        store=fake_store,
    )
    cited = [item for item in evidence if item.kind == "cited"]
    assert cited
    for item in cited:
        if item.text:
            assert item.text in pages[0].text


def test_docs_list_and_search_api(
    client: TestClient, fake_store: ManualStore, sample_pdf: Path
) -> None:
    ingest_pdf(sample_pdf, doc_id="demo_manual", title="Demo Manual", store=fake_store)
    app.dependency_overrides[docs.get_manual_store] = lambda: fake_store
    try:
        listed = client.get("/docs")
        assert listed.status_code == 200, listed.text
        assert any(doc["doc_id"] == "demo_manual" for doc in listed.json())

        search = client.get(
            "/docs/search",
            params={"q": "cooling fan", "doc_id": "demo_manual"},
        )
        assert search.status_code == 200, search.text
        hits = search.json()
        assert hits
        assert hits[0]["doc_id"] == "demo_manual"
    finally:
        app.dependency_overrides.pop(docs.get_manual_store, None)


def test_session_attaches_evidence_for_check(
    client: TestClient, fake_store: ManualStore, sample_pdf: Path
) -> None:
    ingest_pdf(sample_pdf, doc_id="demo_manual", title="Demo Manual", store=fake_store)
    graphs = load_graphs(DEFAULT_GRAPHS_DIR)
    graph = graphs["overtemperature"]
    checks = []
    for check in graph.checks:
        if check.id == "check_fan_operation":
            checks.append(
                check.model_copy(
                    update={
                        "source": Source(
                            doc_id="demo_manual",
                            section="7.3 Fault Codes",
                            page=1,
                        )
                    }
                )
            )
        else:
            checks.append(check)
    patched = graph.model_copy(update={"checks": checks})

    app.dependency_overrides[docs.get_manual_store] = lambda: fake_store
    app.dependency_overrides[graph_loader.get_graphs] = lambda: {
        "overtemperature": patched
    }
    try:
        created = client.post(
            "/sessions",
            json={"fault_id": "overtemperature", "equipment_label": "Bay 1"},
        )
        assert created.status_code == 201, created.text
        action = created.json()["state"]["next_action"]
        assert action["type"] == "check"
        assert action["evidence"]
        assert action["evidence"][0]["kind"] == "cited"
        assert action["evidence"][0]["page"] == 1
        assert action["evidence"][0]["doc_id"] == "demo_manual"
    finally:
        app.dependency_overrides.pop(docs.get_manual_store, None)
        app.dependency_overrides.pop(graph_loader.get_graphs, None)


def test_check_citations_reports_missing_doc_and_page(fake_store: ManualStore) -> None:
    fake_store.registry.upsert_doc(
        doc_id="demo_manual",
        title="Demo",
        filename="demo.pdf",
        page_count=1,
        empty_pages=[],
    )
    graphs = load_graphs(DEFAULT_GRAPHS_DIR)
    graph = graphs["overtemperature"]
    checks = [
        graph.checks[0].model_copy(
            update={"source": Source(doc_id="demo_manual", section="x", page=99)}
        ),
        graph.checks[1].model_copy(
            update={"source": Source(doc_id="not_ingested", section="x", page=1)}
        ),
        *graph.checks[2:],
    ]
    patched = {**graphs, "overtemperature": graph.model_copy(update={"checks": checks})}
    issues = check_citations(patched, fake_store.registry)
    kinds = {issue.kind for issue in issues}
    assert "missing_page" in kinds
    assert "missing_doc" in kinds
    assert any(issue.page == 99 for issue in issues)
    assert any(issue.doc_id == "not_ingested" for issue in issues)


def test_check_citations_skips_tbd(fake_store: ManualStore) -> None:
    graphs = load_graphs(DEFAULT_GRAPHS_DIR)
    assert check_citations(graphs, fake_store.registry) == []


def test_check_citations_cli_exits_nonzero(
    fake_store: ManualStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_store.registry.upsert_doc(
        doc_id="demo_manual",
        title="Demo",
        filename="demo.pdf",
        page_count=1,
        empty_pages=[],
    )
    graphs = load_graphs(DEFAULT_GRAPHS_DIR)
    graph = graphs["overtemperature"]
    checks = [
        graph.checks[0].model_copy(
            update={"source": Source(doc_id="demo_manual", section="x", page=5)}
        ),
        *graph.checks[1:],
    ]
    patched = {"overtemperature": graph.model_copy(update={"checks": checks})}

    # Import after path setup — script lives under backend/scripts.
    import importlib.util

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_citations.py"
    spec = importlib.util.spec_from_file_location("check_citations_cli", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "load_graphs", lambda _dir: patched)
    assert module.main(["--docs-db", str(fake_store.registry.path)]) == 1

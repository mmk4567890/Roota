"""Live Chroma DefaultEmbeddingFunction checks. Run with: pytest --live tests/live"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.engine.schema import Source
from app.retrieval.embeddings import default_embedding_function
from app.retrieval.evidence import get_evidence
from app.retrieval.ingest import ingest_pdf
from app.retrieval.store import ManualStore


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


def test_live_default_embeddings_ingest_and_evidence(tmp_path: Path) -> None:
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
    pdf_path = tmp_path / "manual.pdf"
    pdf_path.write_bytes(_make_pdf([page1, page2]))

    chroma_dir = tmp_path / "chroma"
    docs_db = tmp_path / "docs.db"
    store = ManualStore(
        chroma_dir=chroma_dir,
        docs_db_path=docs_db,
        embedding_function=default_embedding_function(),
    )
    ingest_pdf(pdf_path, doc_id="demo_manual", title="Demo Manual", store=store)

    fan_query = (
        "Observe or measure the cooling fan while the drive is powered and report "
        "whether it runs normally, is stopped, or is noisy."
    )
    fan_evidence = get_evidence(
        Source(doc_id="demo_manual", section="7.3 Fault Codes", page=1),
        fan_query,
        k=3,
        store=store,
    )
    assert fan_evidence
    assert fan_evidence[0].kind == "cited"
    assert fan_evidence[0].page == 1

    load_evidence = get_evidence(
        Source(doc_id="demo_manual", section="7.4", page=1),
        "measure output current as a percentage of rated current load duty",
        k=3,
        store=store,
    )
    related_load = [item for item in load_evidence if item.kind == "related"]
    assert any(item.page == 2 for item in related_load), load_evidence

    # Persistence: reopen the same chroma dir and repeat a query.
    reopened = ManualStore(
        chroma_dir=chroma_dir,
        docs_db_path=docs_db,
        embedding_function=default_embedding_function(),
    )
    again = get_evidence(
        Source(doc_id="demo_manual", section="7.3 Fault Codes", page=1),
        fan_query,
        k=3,
        store=reopened,
    )
    assert again
    assert again[0].kind == "cited"
    assert again[0].page == 1

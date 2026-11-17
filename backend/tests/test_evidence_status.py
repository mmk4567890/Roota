from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.engine.schema import Source
from app.graphs.loader import load_graphs
from tests.graph_fixtures import TEST_GRAPHS_DIR
from app.main import app
from app.retrieval.embeddings import FakeEmbeddingFunction
from app.retrieval.ingest import ingest_pdf
from app.retrieval.store import ManualStore, StoredChunk
from app.routers import docs
from app.routers.sessions import _safe_evidence_error
from app.graphs import loader as graph_loader
from tests.test_retrieval import _make_pdf


def _create_session(client: TestClient) -> dict:
    response = client.post(
        "/sessions",
        json={"fault_id": "overtemperature", "equipment_label": "Bay 9"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_evidence_status_none_for_escalate(client: TestClient) -> None:
    created = _create_session(client)
    session_id = created["id"]
    assert created["state"]["next_action"]["evidence_status"] == "no_manual"

    # Rule everything out so the session escalates (no manual evidence on escalate).
    response = client.post(
        f"/sessions/{session_id}/facts",
        json={
            "facts": {
                "fan_status": "normal",
                "airflow_obstruction": "none",
                "heatsink_condition": "clean",
                "load_percent": 50,
                "ambient_temp_c": 25,
                "carrier_frequency_khz": 4,
            }
        },
    )
    assert response.status_code == 200, response.text
    action = response.json()["state"]["next_action"]
    assert action["type"] == "escalate"
    assert action["evidence_status"] is None
    assert action["evidence"] is None
    assert action["evidence_error"] is None


def test_evidence_status_no_manual_for_tbd(client: TestClient) -> None:
    created = _create_session(client)
    action = created["state"]["next_action"]
    assert action["type"] == "check"
    assert action["source"]["doc_id"] == "TBD_MANUAL"
    assert action["evidence_status"] == "no_manual"
    assert action["evidence"] == []
    assert action["evidence_error"] is None


def test_evidence_status_attached(
    client: TestClient, tmp_path: Path
) -> None:
    store = ManualStore(
        chroma_dir=tmp_path / "chroma",
        docs_db_path=tmp_path / "docs.db",
        embedding_function=FakeEmbeddingFunction(),
    )
    pdf = tmp_path / "manual.pdf"
    pdf.write_bytes(
        _make_pdf(
            [
                "7.3 Fault Codes\nCooling fan inspection while powered. " + ("fan " * 40),
                "7.4 Load\nMeasure rated current load. " + ("load " * 40),
            ]
        )
    )
    ingest_pdf(pdf, doc_id="demo_manual", title="Demo", store=store)

    graphs = load_graphs(TEST_GRAPHS_DIR)
    graph = graphs["overtemperature"]
    checks = [
        graph.checks[0].model_copy(
            update={
                "source": Source(
                    doc_id="demo_manual", section="7.3 Fault Codes", page=1
                )
            }
        ),
        *graph.checks[1:],
    ]
    patched = graph.model_copy(update={"checks": checks})
    app.dependency_overrides[docs.get_manual_store] = lambda: store
    app.dependency_overrides[graph_loader.get_graphs] = lambda: {
        "overtemperature": patched
    }
    try:
        created = _create_session(client)
        action = created["state"]["next_action"]
        assert action["type"] == "check"
        assert action["evidence_status"] == "attached"
        assert action["evidence_error"] is None
        assert action["evidence"]
        assert action["evidence"][0]["kind"] == "cited"
        assert action["check"]["id"] == "check_fan_operation"
    finally:
        app.dependency_overrides.pop(docs.get_manual_store, None)
        app.dependency_overrides.pop(graph_loader.get_graphs, None)


class _SearchRaisesStore:
    def has_doc(self, doc_id: str) -> bool:
        return True

    def get_chunks_for_page(self, doc_id: str, page: int) -> list[StoredChunk]:
        return []

    def search(self, *args: object, **kwargs: object) -> list[StoredChunk]:
        raise RuntimeError(
            "embedding failed reading C:\\Users\\secret\\.cache\\chroma\\model"
        )


class _ChunksRaiseStore:
    def has_doc(self, doc_id: str) -> bool:
        return True

    def get_chunks_for_page(self, doc_id: str, page: int) -> list[StoredChunk]:
        raise OSError("cannot open /home/plant/chroma/sqlite")

    def search(self, *args: object, **kwargs: object) -> list[StoredChunk]:
        raise AssertionError("search must not run when get_chunks_for_page fails")


def _session_with_ingested_source(
    client: TestClient, store: object
) -> tuple[str, str]:
    graphs = load_graphs(TEST_GRAPHS_DIR)
    graph = graphs["overtemperature"]
    checks = [
        graph.checks[0].model_copy(
            update={
                "source": Source(doc_id="demo_manual", section="7.3", page=1)
            }
        ),
        *graph.checks[1:],
    ]
    patched = graph.model_copy(update={"checks": checks})
    app.dependency_overrides[docs.get_manual_store] = lambda: store  # type: ignore[arg-type,return-value]
    app.dependency_overrides[graph_loader.get_graphs] = lambda: {
        "overtemperature": patched
    }
    created = _create_session(client)
    return created["id"], created["state"]["next_action"]["check"]["id"]


def test_evidence_status_unavailable_when_search_raises(
    client: TestClient,
) -> None:
    store = _SearchRaisesStore()
    try:
        session_id, check_id = _session_with_ingested_source(client, store)
        response = client.get(f"/sessions/{session_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        action = body["state"]["next_action"]
        assert action["type"] == "check"
        assert action["check"]["id"] == check_id
        assert action["evidence_status"] == "unavailable"
        assert action["evidence"] is None
        assert action["evidence_error"] == "RuntimeError: retrieval failed"
        assert "Users" not in (action["evidence_error"] or "")
        assert "secret" not in (action["evidence_error"] or "")
        assert "C:\\" not in (action["evidence_error"] or "")
    finally:
        app.dependency_overrides.pop(docs.get_manual_store, None)
        app.dependency_overrides.pop(graph_loader.get_graphs, None)


def test_evidence_status_unavailable_when_get_chunks_raises(
    client: TestClient,
) -> None:
    store = _ChunksRaiseStore()
    try:
        session_id, check_id = _session_with_ingested_source(client, store)
        response = client.get(f"/sessions/{session_id}")
        assert response.status_code == 200, response.text
        action = response.json()["state"]["next_action"]
        assert action["check"]["id"] == check_id
        assert action["evidence_status"] == "unavailable"
        assert action["evidence"] is None
        assert action["evidence_error"] == "OSError: retrieval failed"
        assert "/home/" not in (action["evidence_error"] or "")
        assert "plant" not in (action["evidence_error"] or "")
    finally:
        app.dependency_overrides.pop(docs.get_manual_store, None)
        app.dependency_overrides.pop(graph_loader.get_graphs, None)


def test_safe_evidence_error_never_includes_exception_text() -> None:
    err = RuntimeError("key=sk-secret path=/Users/me/.cache/chroma")
    message = _safe_evidence_error(err)
    assert message == "RuntimeError: retrieval failed"
    assert "sk-secret" not in message
    assert "/Users/" not in message

    class EmbeddingLoadError(Exception):
        pass

    assert (
        _safe_evidence_error(EmbeddingLoadError("onnx missing at /home/x"))
        == "EmbeddingLoadError: embedding model not available"
    )

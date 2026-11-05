"""Regression tests for the Prompt 6b review fixes: request shape accepted by
current models, OS trust store for outbound TLS, and a prefetch that works."""

from __future__ import annotations

import hashlib
import ssl
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.engine.schema import FaultGraph
from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.parser import anthropic_parser
from app.parser.anthropic_parser import EFFORT, MAX_TOKENS, TOOL_NAME, AnthropicParser
from app.parser.base import ParseError
from app.retrieval import prefetch
from app.routers import sessions
from app.tls import system_ssl_context


@pytest.fixture
def overtemperature() -> FaultGraph:
    return load_graphs(DEFAULT_GRAPHS_DIR)["overtemperature"]


def _response(stop_reason: str, tool_input: dict[str, Any] | None) -> MagicMock:
    response = MagicMock()
    response.stop_reason = stop_reason
    blocks = []
    if tool_input is not None:
        block = MagicMock()
        block.type = "tool_use"
        block.name = TOOL_NAME
        block.input = tool_input
        blocks.append(block)
    response.content = blocks
    return response


# --- request shape: current models reject forced tool choice ---


def test_request_never_forces_a_tool(overtemperature: FaultGraph) -> None:
    stub = MagicMock()
    stub.messages.create.return_value = _response("tool_use", {})

    AnthropicParser(client=stub).parse("fan ok", overtemperature, [])

    kwargs = stub.messages.create.call_args.kwargs
    # {"type": "tool"} / {"type": "any"} are a 400 on Claude Sonnet 5.5 / Opus 5.5.
    assert kwargs["tool_choice"] == {"type": "auto"}
    assert kwargs["max_tokens"] == MAX_TOKENS
    assert kwargs["extra_body"] == {"output_config": {"effort": EFFORT}}


def test_system_prompt_requires_the_tool_call(overtemperature: FaultGraph) -> None:
    system = AnthropicParser(client=MagicMock()).build_system_prompt(overtemperature)
    assert f"Always respond by calling the {TOOL_NAME} tool exactly once" in system
    assert "call it with an empty object" in system


@pytest.mark.parametrize(
    ("stop_reason", "message"),
    [
        ("refusal", "declined"),
        ("max_tokens", "ran out of output tokens"),
    ],
)
def test_incomplete_responses_are_parse_errors(
    overtemperature: FaultGraph, stop_reason: str, message: str
) -> None:
    stub = MagicMock()
    # Even with a partial tool call present, these responses are not trusted.
    stub.messages.create.return_value = _response(stop_reason, {"fan_status": "normal"})

    with pytest.raises(ParseError, match=message):
        AnthropicParser(client=stub).parse("fan ok", overtemperature, [])


def test_text_only_answer_is_502_and_records_nothing(client: TestClient) -> None:
    stub = MagicMock()
    stub.messages.create.return_value = _response("end_turn", None)
    client.app.dependency_overrides[sessions.get_parser] = lambda: AnthropicParser(client=stub)
    session_id = client.post(
        "/sessions", json={"fault_id": "overtemperature", "equipment_label": "Bay 1"}
    ).json()["id"]

    response = client.post(f"/sessions/{session_id}/observations", json={"text": "fan ok"})

    assert response.status_code == 502
    assert "no report_observation_fields tool call" in response.json()["detail"]
    assert client.get(f"/sessions/{session_id}").json()["events"] == []


# --- outbound TLS uses the OS trust store, with verification on ---


def test_system_ssl_context_verifies() -> None:
    context = system_ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_anthropic_client_uses_system_trust_store(monkeypatch: pytest.MonkeyPatch) -> None:
    import anthropic

    sentinel = system_ssl_context()
    monkeypatch.setattr(anthropic_parser, "system_ssl_context", lambda: sentinel)
    captured: dict[str, Any] = {}
    real = anthropic.DefaultHttpxClient

    def recording_client(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(anthropic, "DefaultHttpxClient", recording_client)

    parser = AnthropicParser(api_key="test-key-not-real")

    assert captured["verify"] is sentinel
    parser._client.close()


# --- prefetch ---


def _patch_download(
    monkeypatch: pytest.MonkeyPatch, payload: bytes, expected_sha: str
) -> list[dict[str, Any]]:
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    monkeypatch.setattr(ONNXMiniLM_L6_V2, "_MODEL_SHA256", expected_sha)
    calls: list[dict[str, Any]] = []
    real_client = httpx.Client

    def fake_client(**kwargs: Any) -> httpx.Client:
        calls.append(kwargs)
        transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload))
        return real_client(transport=transport)

    monkeypatch.setattr(prefetch.httpx, "Client", fake_client)
    return calls


def test_download_archive_keeps_file_when_hash_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"model-archive-bytes"
    calls = _patch_download(monkeypatch, payload, hashlib.sha256(payload).hexdigest())

    archive = prefetch.download_archive(tmp_path)

    assert archive.read_bytes() == payload
    assert not list(tmp_path.glob("*.part"))
    assert isinstance(calls[0]["verify"], ssl.SSLContext)
    assert calls[0]["verify"].verify_mode == ssl.CERT_REQUIRED


def test_download_archive_rejects_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_download(monkeypatch, b"tampered", "0" * 64)

    with pytest.raises(RuntimeError, match="SHA-256"):
        prefetch.download_archive(tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_embed_probe_accepts_numpy_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    # Chroma returns numpy arrays; `not array` raised ValueError before the fix,
    # so prefetch failed on every machine.
    class FakeDefault:
        def __call__(self, texts: list[str]) -> list[np.ndarray]:
            return [np.ones(384, dtype=np.float32)]

    import chromadb.utils.embedding_functions as functions

    monkeypatch.setattr(functions, "DefaultEmbeddingFunction", FakeDefault)

    _, size = prefetch.embed_probe()

    assert size == 384


def test_embed_probe_rejects_empty_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    class EmptyDefault:
        def __call__(self, texts: list[str]) -> list[np.ndarray]:
            return [np.array([], dtype=np.float32)]

    import chromadb.utils.embedding_functions as functions

    monkeypatch.setattr(functions, "DefaultEmbeddingFunction", EmptyDefault)

    with pytest.raises(RuntimeError, match="empty vector"):
        prefetch.embed_probe()


def test_prefetch_downloads_only_when_model_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    downloads: list[Path] = []
    monkeypatch.setattr(prefetch, "default_model_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(prefetch, "download_archive", lambda cache_dir: downloads.append(cache_dir))
    monkeypatch.setattr(prefetch, "embed_probe", lambda: (tmp_path, 384))

    monkeypatch.setattr(prefetch, "model_files_present", lambda cache_dir: False)
    assert prefetch.main([]) == 0
    monkeypatch.setattr(prefetch, "model_files_present", lambda cache_dir: True)
    assert prefetch.main([]) == 0

    assert downloads == [tmp_path]

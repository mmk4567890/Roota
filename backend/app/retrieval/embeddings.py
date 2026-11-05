from __future__ import annotations

from typing import Any


def _hash_embed(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    lowered = text.lower()
    if not lowered:
        return vector
    for index, char in enumerate(lowered):
        bucket = (ord(char) + index) % dimensions
        vector[bucket] += 1.0
    for index in range(len(lowered) - 1):
        bigram = lowered[index : index + 2]
        bucket = (ord(bigram[0]) * 31 + ord(bigram[1])) % dimensions
        vector[bucket] += 0.5
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class FakeEmbeddingFunction:
    """Tiny deterministic embeddings for tests — no network, no model download.

    Implements the chromadb EmbeddingFunction surface so collection creation
    accepts it without treating it as a legacy function.
    """

    def __init__(self, dimensions: int = 8) -> None:
        if dimensions < 2:
            raise ValueError("dimensions must be >= 2")
        self._dimensions = dimensions

    @staticmethod
    def name() -> str:
        return "roota_fake_embedding"

    def get_config(self) -> dict[str, Any]:
        return {"dimensions": self._dimensions}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> FakeEmbeddingFunction:
        return FakeEmbeddingFunction(dimensions=int(config.get("dimensions", 8)))

    def is_legacy(self) -> bool:
        return False

    def supported_spaces(self) -> list[str]:
        return ["cosine", "l2", "ip"]

    def default_space(self) -> str:
        return "cosine"

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [_hash_embed(text, self._dimensions) for text in input]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)


def default_embedding_function() -> Any:
    """Chroma's default local embedding function (may download a model once)."""
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    return DefaultEmbeddingFunction()

"""Prefetch or check Chroma's default local embedding model.

Plant-floor machines are often offline. Run ``python -m app.retrieval.prefetch``
once on a connected machine so the ONNX model is cached under the user profile
before taking Roota offline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def default_model_cache_dir() -> Path:
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    return Path(ONNXMiniLM_L6_V2.DOWNLOAD_PATH)


def model_files_present(cache_dir: Path | None = None) -> bool:
    """True when the extracted ONNX model + tokenizer are already on disk."""
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    root = cache_dir if cache_dir is not None else default_model_cache_dir()
    extracted = root / ONNXMiniLM_L6_V2.EXTRACTED_FOLDER_NAME
    return (extracted / "model.onnx").is_file() and (extracted / "tokenizer.json").is_file()


def embed_probe() -> tuple[Path, int]:
    """Load DefaultEmbeddingFunction and embed one string. May download the model."""
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    cache_dir = default_model_cache_dir()
    vectors = DefaultEmbeddingFunction()(["roota embedding prefetch probe"])
    if not vectors or not vectors[0]:
        raise RuntimeError("DefaultEmbeddingFunction returned an empty vector")
    return cache_dir, len(vectors[0])


def run_check() -> int:
    """Exit 0 if the cached model loads without needing a download; else 1."""
    cache_dir = default_model_cache_dir()
    if not model_files_present(cache_dir):
        print(
            "Embedding model is not cached for offline use.\n"
            f"Expected files under: {cache_dir}\n"
            "Run `python -m app.retrieval.prefetch` on a machine with network access."
        )
        return 1
    try:
        _, size = embed_probe()
    except Exception as error:
        print(
            f"Cached embedding model failed to load ({type(error).__name__}).\n"
            f"Cache dir: {cache_dir}\n"
            "Re-run `python -m app.retrieval.prefetch` on a connected machine."
        )
        return 1
    print(
        f"Embedding model OK (offline). cache={cache_dir} vector_size={size}"
    )
    return 0


def run_prefetch() -> int:
    """Download/load the model and print cache location + vector size."""
    cache_dir = default_model_cache_dir()
    print(f"Loading Chroma DefaultEmbeddingFunction (cache={cache_dir})...")
    try:
        resolved, size = embed_probe()
    except Exception as error:
        print(
            f"Failed to download or load the embedding model ({type(error).__name__}).\n"
            "Check network access and that onnxruntime is installed."
        )
        return 1
    print(f"Embedding model ready. cache={resolved} vector_size={size}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prefetch Chroma's local embedding model for offline Roota deployments."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 if the model is already usable offline; do not download.",
    )
    args = parser.parse_args(argv)
    if args.check:
        return run_check()
    return run_prefetch()


if __name__ == "__main__":
    raise SystemExit(main())

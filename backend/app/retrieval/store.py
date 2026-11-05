from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.retrieval.embeddings import default_embedding_function


class EmbeddingFunction(Protocol):
    def __call__(self, input: list[str]) -> list[list[float]]:
        ...

COLLECTION_NAME = "manuals"
DOC_ID_PATTERN = re.compile(r"^[a-z0-9_-]{1,64}$")
TBD_MANUAL = "TBD_MANUAL"


@dataclass(frozen=True)
class DocRecord:
    doc_id: str
    title: str
    filename: str
    page_count: int
    empty_pages: tuple[int, ...]  # pages with no extractable text (scanned)


@dataclass(frozen=True)
class StoredChunk:
    chunk_id: str
    doc_id: str
    title: str
    page: int
    section: str
    text: str


def default_chroma_dir() -> Path:
    configured = os.environ.get("ROOTA_CHROMA_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "data" / "chroma"


def default_docs_db_path() -> Path:
    configured = os.environ.get("ROOTA_DOCS_DB_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "data" / "docs.db"


def validate_doc_id(doc_id: str) -> str:
    if not DOC_ID_PATTERN.fullmatch(doc_id):
        raise ValueError(
            f"invalid doc_id '{doc_id}': must match {DOC_ID_PATTERN.pattern}"
        )
    return doc_id


class DocsRegistry:
    """SQLite registry of ingested manuals (doc_id, title, filename, pages).

    Separate from Chroma so tools that only need page counts (check_citations)
    never open the vector collection, which refuses an embedding function other
    than the one it was created with.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else default_docs_db_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @property
    def path(self) -> Path:
        return self._path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS docs (
                    doc_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    empty_pages TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(docs)")}
            if "empty_pages" not in columns:
                # Registry created before empty pages were recorded.
                connection.execute(
                    "ALTER TABLE docs ADD COLUMN empty_pages TEXT NOT NULL DEFAULT '[]'"
                )

    def has_doc(self, doc_id: str) -> bool:
        return self.get_doc(doc_id) is not None

    def get_doc(self, doc_id: str) -> DocRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT doc_id, title, filename, page_count, empty_pages FROM docs WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_doc(row)

    def list_docs(self) -> list[DocRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT doc_id, title, filename, page_count, empty_pages
                FROM docs
                ORDER BY doc_id ASC
                """
            ).fetchall()
        return [_row_to_doc(row) for row in rows]

    def upsert_doc(
        self,
        *,
        doc_id: str,
        title: str,
        filename: str,
        page_count: int,
        empty_pages: list[int],
    ) -> None:
        validate_doc_id(doc_id)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO docs (doc_id, title, filename, page_count, empty_pages)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    title = excluded.title,
                    filename = excluded.filename,
                    page_count = excluded.page_count,
                    empty_pages = excluded.empty_pages
                """,
                (doc_id, title, filename, page_count, json.dumps(sorted(empty_pages))),
            )

    def remove(self, doc_id: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM docs WHERE doc_id = ?", (doc_id,))

class ManualStore:
    """Persistent Chroma collection + SQLite docs registry for manuals."""

    def __init__(
        self,
        *,
        chroma_dir: Path | str | None = None,
        docs_db_path: Path | str | None = None,
        embedding_function: EmbeddingFunction | None = None,
    ) -> None:
        self._chroma_dir = Path(chroma_dir) if chroma_dir is not None else default_chroma_dir()
        self._chroma_dir.mkdir(parents=True, exist_ok=True)
        self._registry = DocsRegistry(docs_db_path)

        import warnings

        # chromadb emits DeprecationWarning on Python 3.14 via asyncio.iscoroutinefunction.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r".*asyncio\.iscoroutinefunction.*",
                category=DeprecationWarning,
            )
            import chromadb

        self._client = chromadb.PersistentClient(path=str(self._chroma_dir))
        ef = (
            embedding_function
            if embedding_function is not None
            else default_embedding_function()
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,  # type: ignore[arg-type]
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def chroma_dir(self) -> Path:
        return self._chroma_dir

    @property
    def registry(self) -> DocsRegistry:
        return self._registry

    def has_doc(self, doc_id: str) -> bool:
        return self._registry.has_doc(doc_id)

    def get_doc(self, doc_id: str) -> DocRecord | None:
        return self._registry.get_doc(doc_id)

    def list_docs(self) -> list[DocRecord]:
        return self._registry.list_docs()


    def delete_doc_chunks(self, doc_id: str) -> None:
        """Remove all chunks for doc_id so re-ingest is idempotent."""
        existing = self._collection.get(where={"doc_id": doc_id})
        ids = existing.get("ids") or []
        if ids:
            self._collection.delete(ids=ids)

    def replace_chunks(
        self,
        *,
        doc_id: str,
        title: str,
        filename: str,
        page_count: int,
        empty_pages: list[int],
        chunks: list[StoredChunk],
    ) -> int:
        """Replace all chunks for a document. Returns the new chunk count.

        Chroma has no transactions, so the registry row goes first and comes
        back last: if adding chunks fails, the doc reads as "not ingested"
        (evidence returns [], check_citations flags it) instead of claiming
        pages whose chunks were already deleted.
        """
        validate_doc_id(doc_id)
        self._registry.remove(doc_id)
        self.delete_doc_chunks(doc_id)
        if chunks:
            self._collection.add(
                ids=[chunk.chunk_id for chunk in chunks],
                documents=[chunk.text for chunk in chunks],
                metadatas=[
                    {
                        "doc_id": chunk.doc_id,
                        "title": chunk.title,
                        "page": chunk.page,
                        "section": chunk.section,
                    }
                    for chunk in chunks
                ],
            )
        self._registry.upsert_doc(
            doc_id=doc_id,
            title=title,
            filename=filename,
            page_count=page_count,
            empty_pages=empty_pages,
        )
        return len(chunks)

    def count_chunks(self, doc_id: str) -> int:
        result = self._collection.get(where={"doc_id": doc_id})
        return len(result.get("ids") or [])

    def get_chunks_for_page(self, doc_id: str, page: int) -> list[StoredChunk]:
        result = self._collection.get(
            where={"$and": [{"doc_id": doc_id}, {"page": page}]},
            include=["documents", "metadatas"],
        )
        return _rows_to_chunks(result)

    def search(
        self,
        query: str,
        *,
        doc_id: str | None = None,
        page: int | None = None,
        k: int = 5,
        exclude_ids: set[str] | None = None,
    ) -> list[StoredChunk]:
        if k < 1:
            raise ValueError("k must be >= 1")
        if page is not None and not doc_id:
            raise ValueError("page filter requires doc_id")
        where: dict[str, Any] | None = {"doc_id": doc_id} if doc_id else None
        if page is not None:
            where = {"$and": [{"doc_id": doc_id}, {"page": page}]}
        # Fetch extra when excluding so we can still return k results.
        exclude = exclude_ids or set()
        n_results = k + len(exclude)
        total = self._collection.count()
        if total == 0:
            return []
        n_results = min(n_results, total)
        result = self._collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        chunks: list[StoredChunk] = []
        for chunk_id, text, metadata in zip(ids, documents, metadatas, strict=True):
            if chunk_id in exclude:
                continue
            meta = metadata or {}
            chunks.append(
                StoredChunk(
                    chunk_id=chunk_id,
                    doc_id=str(meta.get("doc_id", "")),
                    title=str(meta.get("title", "")),
                    page=int(meta.get("page", 0)),
                    section=str(meta.get("section", "")),
                    text=text or "",
                )
            )
            if len(chunks) >= k:
                break
        return chunks


def _row_to_doc(row: sqlite3.Row) -> DocRecord:
    return DocRecord(
        doc_id=row["doc_id"],
        title=row["title"],
        filename=row["filename"],
        page_count=int(row["page_count"]),
        empty_pages=tuple(json.loads(row["empty_pages"])),
    )


def _rows_to_chunks(result: dict[str, Any]) -> list[StoredChunk]:
    ids = result.get("ids") or []
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    chunks: list[StoredChunk] = []
    for chunk_id, text, metadata in zip(ids, documents, metadatas, strict=True):
        meta = metadata or {}
        chunks.append(
            StoredChunk(
                chunk_id=chunk_id,
                doc_id=str(meta.get("doc_id", "")),
                title=str(meta.get("title", "")),
                page=int(meta.get("page", 0)),
                section=str(meta.get("section", "")),
                text=text or "",
            )
        )
    chunks.sort(key=lambda item: (item.page, item.chunk_id))
    return chunks

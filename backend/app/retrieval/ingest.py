from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.retrieval.store import ManualStore, StoredChunk, validate_doc_id

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
# Numbered headings like "7.3 Fault Codes" or "4.1.2 Cooling fan". The title
# must start with a capitalised word of 3+ letters so spec lines such as
# "1.5 kW rated output" or "2.2 Nm on terminals" are not taken for headings.
# The ACS580 manual's fault tables are matched by ENTRY_START_RE below.
# A fault or warning table entry starts a line with its 4-digit hex code and a
# capitalised name ("4210 IGBT overtemperature", "A581 Fan"). Auxiliary codes
# under an entry ("0002 Motor is rotating ...") start with 000 and stay with
# their parent entry. Chunks start at entries so a cited passage opens at its
# own fault code instead of mid-way through the previous one.
ENTRY_START_RE = re.compile(r"^(?!000)[0-9A-F]{4} [A-Z]", re.MULTILINE)
SECTION_HEADING_RE = re.compile(r"^\d+(?:\.\d+)+\s+[A-Z][A-Za-z]{2,}.*$")


@dataclass(frozen=True)
class PageExtract:
    page: int  # 1-based manual page number
    text: str
    empty: bool


@dataclass(frozen=True)
class IngestResult:
    doc_id: str
    title: str
    filename: str
    page_count: int
    chunk_count: int
    empty_pages: list[int]


def extract_pages(pdf_path: Path) -> list[PageExtract]:
    """Extract text page by page. Empty/scanned pages are kept as empty strings."""
    reader = PdfReader(str(pdf_path))
    pages: list[PageExtract] = []
    for index, page in enumerate(reader.pages):
        raw = page.extract_text()
        text = raw if raw is not None else ""
        # Normalise newlines; keep content otherwise verbatim.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        pages.append(
            PageExtract(
                page=index + 1,
                text=text,
                empty=not text.strip(),
            )
        )
    return pages


def detect_section(page_text: str, end: int) -> str:
    """Return the last numbered heading line at or before ``end``, or \"\"."""
    last = ""
    for line in page_text[:end].splitlines():
        stripped = line.strip()
        if SECTION_HEADING_RE.match(stripped):
            last = stripped
    return last


def chunk_page_text(
    page_text: str,
    *,
    page: int,
    doc_id: str,
    title: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[StoredChunk]:
    """Chunk a single page. Never spans pages. An empty page yields no chunks.

    A blank chunk would come back from search as an empty "related" passage;
    empty pages are recorded in the docs registry instead (``empty_pages``).
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    if not page_text.strip():
        return []

    chunks: list[StoredChunk] = []
    index = 0
    for segment_start, segment_end in _entry_segments(page_text):
        start = segment_start
        while start < segment_end:
            end = min(start + chunk_size, segment_end)
            piece = page_text[start:end]
            if piece.strip():
                chunks.append(
                    StoredChunk(
                        chunk_id=f"{doc_id}::p{page}::c{index}",
                        doc_id=doc_id,
                        title=title,
                        page=page,
                        section=detect_section(page_text, end),
                        text=piece,
                    )
                )
                index += 1
            if end >= segment_end:
                break
            start = end - overlap
    return chunks


def _entry_segments(page_text: str) -> list[tuple[int, int]]:
    """Split a page at fault/warning entry starts; the page itself if none."""
    starts = [match.start() for match in ENTRY_START_RE.finditer(page_text)]
    bounds = sorted({0, *starts})
    return list(zip(bounds, [*bounds[1:], len(page_text)], strict=True))


def build_chunks(
    pages: list[PageExtract],
    *,
    doc_id: str,
    title: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[StoredChunk]:
    chunks: list[StoredChunk] = []
    for page in pages:
        chunks.extend(
            chunk_page_text(
                page.text,
                page=page.page,
                doc_id=doc_id,
                title=title,
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )
    return chunks


def ingest_pdf(
    pdf_path: Path | str,
    *,
    doc_id: str,
    title: str,
    store: ManualStore,
) -> IngestResult:
    """Extract, chunk, and replace all stored content for ``doc_id``."""
    validate_doc_id(doc_id)
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    pages = extract_pages(path)
    empty_pages = [page.page for page in pages if page.empty]
    chunks = build_chunks(pages, doc_id=doc_id, title=title)
    chunk_count = store.replace_chunks(
        doc_id=doc_id,
        title=title,
        filename=path.name,
        page_count=len(pages),
        empty_pages=empty_pages,
        chunks=chunks,
    )
    return IngestResult(
        doc_id=doc_id,
        title=title,
        filename=path.name,
        page_count=len(pages),
        chunk_count=chunk_count,
        empty_pages=empty_pages,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest a PDF manual into Roota's manuals collection."
    )
    parser.add_argument("pdf", type=Path, help="Path to the PDF file")
    parser.add_argument("--doc-id", required=True, help="Stable document id (a-z0-9_-)")
    parser.add_argument("--title", required=True, help="Human-readable document title")
    args = parser.parse_args(argv)

    try:
        validate_doc_id(args.doc_id)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    store = ManualStore()
    try:
        result = ingest_pdf(
            args.pdf,
            doc_id=args.doc_id,
            title=args.title,
            store=store,
        )
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"Ingested doc_id={result.doc_id!r} title={result.title!r} "
        f"pages={result.page_count} chunks={result.chunk_count}"
    )
    if result.empty_pages:
        pages = ", ".join(str(page) for page in result.empty_pages)
        print(
            f"warning: {len(result.empty_pages)} page(s) with no extractable text "
            f"(recorded as empty): {pages}"
        )
    else:
        print("All pages had extractable text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

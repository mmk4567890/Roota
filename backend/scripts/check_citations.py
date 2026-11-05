#!/usr/bin/env python3
"""List graph Source citations that point at missing docs or pages.

For every Source in the loaded fault graphs:
- doc_id TBD_MANUAL is skipped (placeholder, not yet ingested)
- doc_id not in the docs registry -> missing doc
- doc_id ingested but page is None, < 1, or > page_count -> missing page

Exit code 1 when any problem is found; 0 when clean.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs
from app.retrieval.citations import check_citations
from app.retrieval.embeddings import FakeEmbeddingFunction
from app.retrieval.store import ManualStore, default_docs_db_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graphs-dir",
        type=Path,
        default=DEFAULT_GRAPHS_DIR,
        help="Directory of fault graph JSON files",
    )
    parser.add_argument(
        "--docs-db",
        type=Path,
        default=None,
        help=f"Docs registry SQLite path (default: {default_docs_db_path()})",
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=None,
        help="Chroma dir (only needed so ManualStore can open; registry is authoritative)",
    )
    args = parser.parse_args(argv)

    graphs = load_graphs(args.graphs_dir)
    store_kwargs: dict = {
        "embedding_function": FakeEmbeddingFunction(),
    }
    if args.docs_db is not None:
        store_kwargs["docs_db_path"] = args.docs_db
    if args.chroma_dir is not None:
        store_kwargs["chroma_dir"] = args.chroma_dir

    store = ManualStore(**store_kwargs)
    issues = check_citations(graphs, store)

    if not issues:
        print("OK: all ingested-doc citations point at existing pages.")
        return 0

    print(f"Found {len(issues)} citation issue(s):")
    for issue in issues:
        print(
            f"  [{issue.kind}] fault={issue.fault_id} {issue.location} "
            f"doc_id={issue.doc_id!r} page={issue.page}: {issue.detail}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

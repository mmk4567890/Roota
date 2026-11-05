#!/usr/bin/env python3
"""List graph Source citations that point at missing docs or pages.

For every Source in the loaded fault graphs:
- doc_id TBD_MANUAL is skipped (placeholder, not yet ingested)
- doc_id not in the docs registry -> missing doc
- doc_id ingested but page is None, < 1, or > page_count -> missing page
- cited page has no extractable text (scanned) -> empty page

Reads only the SQLite docs registry, never the Chroma collection.

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
from app.retrieval.store import DocsRegistry, default_docs_db_path


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
    args = parser.parse_args(argv)

    graphs = load_graphs(args.graphs_dir)
    issues = check_citations(graphs, DocsRegistry(args.docs_db))

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

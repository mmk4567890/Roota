"""``python -m app.retrieval`` shows help for ingest / prefetch subcommands."""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "Roota retrieval helpers:\n"
        "  python -m app.retrieval.ingest <pdf> --doc-id <id> --title <title>\n"
        "  python -m app.retrieval.prefetch [--check]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

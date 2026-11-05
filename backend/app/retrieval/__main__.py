"""``python -m app.retrieval`` delegates to the ingest CLI."""

from app.retrieval.ingest import main

if __name__ == "__main__":
    raise SystemExit(main())

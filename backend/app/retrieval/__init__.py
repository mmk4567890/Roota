"""Manual ingestion and verbatim evidence retrieval.

Evidence text is always taken from the stored manual chunks — never summarised
or rewritten by an LLM.
"""

from app.retrieval.evidence import get_evidence
from app.retrieval.store import ManualStore, default_chroma_dir, default_docs_db_path

__all__ = [
    "ManualStore",
    "default_chroma_dir",
    "default_docs_db_path",
    "get_evidence",
]

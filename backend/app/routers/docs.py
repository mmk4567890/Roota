from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict

from app.retrieval.store import ManualStore

router = APIRouter(tags=["docs"])


def get_manual_store(request: Request) -> ManualStore:
    """The ManualStore main's lifespan built."""
    store = getattr(request.app.state, "manual_store", None)
    if store is None:
        raise RuntimeError("Manual store was not configured")
    return store


class DocInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    filename: str
    page_count: int
    empty_pages: list[int]


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    page: int
    section: str
    text: str


@router.get("/docs", response_model=list[DocInfo])
def list_docs(store: ManualStore = Depends(get_manual_store)) -> list[DocInfo]:
    return [
        DocInfo(
            doc_id=doc.doc_id,
            title=doc.title,
            filename=doc.filename,
            page_count=doc.page_count,
            empty_pages=list(doc.empty_pages),
        )
        for doc in store.list_docs()
    ]


@router.get("/docs/search", response_model=list[SearchHit])
def search_docs(
    q: str = Query(..., min_length=1, max_length=500),
    doc_id: str | None = Query(default=None),
    k: int = Query(default=5, ge=1, le=20),
    store: ManualStore = Depends(get_manual_store),
) -> list[SearchHit]:
    query = q.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="q must not be blank",
        )
    if doc_id is not None and not store.has_doc(doc_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown doc_id '{doc_id}'",
        )
    hits = store.search(query, doc_id=doc_id, k=k)
    return [
        SearchHit(
            doc_id=hit.doc_id,
            title=hit.title,
            page=hit.page,
            section=hit.section,
            text=hit.text,
        )
        for hit in hits
    ]

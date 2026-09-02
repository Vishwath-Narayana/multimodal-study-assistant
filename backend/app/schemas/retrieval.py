"""Request/response schemas for the Phase 2 research/debug retrieval API.

Mirrors `app.schemas.documents`'s style: thin Pydantic models, no business
logic. `content_preview` is truncated (never the full chunk content or any
file path) — this endpoint is for research/debugging, not for exposing
arbitrary document internals (see docs/research/security.md).
"""

from __future__ import annotations

from pydantic import BaseModel

_PREVIEW_CHARS = 280


class SearchRequest(BaseModel):
    query: str
    mode: str
    top_k: int = 5


class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    rank: int
    score: float
    retrieval_source: str
    page: int | None = None
    section: str | None = None
    content_preview: str
    bm25_rank: int | None = None
    bm25_score: float | None = None
    dense_rank: int | None = None
    dense_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


class TimingResponse(BaseModel):
    query_embedding_ms: float | None = None
    bm25_ms: float | None = None
    faiss_ms: float | None = None
    hyde_ms: float | None = None
    rrf_ms: float | None = None
    reranking_ms: float | None = None
    total_ms: float


class SearchResponse(BaseModel):
    query: str
    mode: str
    request_id: str
    hyde_query: str | None = None
    results: list[SearchResultItem]
    timing: TimingResponse


def preview(content: str) -> str:
    if len(content) <= _PREVIEW_CHARS:
        return content
    return content[:_PREVIEW_CHARS].rstrip() + "…"

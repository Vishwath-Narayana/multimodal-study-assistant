from __future__ import annotations

from app.retrieval.models import RetrievalResult, RetrievalSource


def make_result(
    chunk_id: str,
    content: str,
    document_id: str = "doc-1",
    rank: int = 1,
    score: float = 1.0,
    retrieval_source: RetrievalSource = RetrievalSource.RERANKER,
    page: int | None = None,
    section: str | None = None,
    rerank_score: float | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        score=score,
        rank=rank,
        retrieval_source=retrieval_source,
        page=page,
        section=section,
        rerank_score=rerank_score,
    )

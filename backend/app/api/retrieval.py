"""Research/debug retrieval endpoint.

Kept thin per the ingestion API's own convention (`app/api/documents.py`):
request handling and dependency wiring only, no retrieval algorithm lives
here — all of it is in `app.retrieval.*`. This is explicitly a
research/debug endpoint (`POST /retrieval/search`), not the final chat/
answer API — Phase 2 is retrieval only (see docs/architecture/retrieval.md
"Scope Boundary").
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.ingestion.repository import ChunkRepository, get_connection, init_db
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.embeddings import BGEEmbeddingProvider, EmbeddingProvider
from app.retrieval.errors import (
    EmbeddingModelError,
    EmptyQueryError,
    HyDEUnavailableError,
    InvalidModeError,
    NoIndexedChunksError,
    RerankerModelError,
    RetrievalError,
)
from app.retrieval.faiss_index import FaissIndexStore
from app.retrieval.hyde import HyDEExpander
from app.retrieval.interfaces import QueryExpander, Reranker
from app.retrieval.llm_client import OllamaClient
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.rrf import RRFFusion
from app.retrieval.service import RetrievalService, RetrievalServiceConfig
from app.schemas.retrieval import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    TimingResponse,
    preview,
)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])

# Heavy ML models (BGE embeddings, the cross-encoder reranker) are loaded
# once per process and reused across requests — reloading a
# sentence-transformers model per HTTP request would be prohibitively slow.
# Keyed by model name so a settings change (unusual, but possible across
# test runs with different fixtures) still gets the right instance rather
# than a stale cached one.
_embedding_provider_cache: dict[str, EmbeddingProvider] = {}
_reranker_cache: dict[str, Reranker] = {}


def reset_model_caches() -> None:
    """Test-only hook: clear cached model singletons between test runs that
    swap in dependency overrides for different settings."""
    _embedding_provider_cache.clear()
    _reranker_cache.clear()


def _get_connection(
    settings: Settings = Depends(get_settings),
) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(settings.sqlite_path)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


def get_bm25_retriever(
    conn: sqlite3.Connection = Depends(_get_connection),
) -> BM25Retriever:
    """Built fresh per request. BM25 index construction over a study-notes
    corpus is fast (milliseconds), so this favours always-correct-and-simple
    over a caching layer with invalidation logic, for a research/debug
    endpoint that is not on a production hot path."""
    chunks = ChunkRepository(conn).list_all()
    return BM25Retriever.from_chunks(chunks)


def get_embedding_provider(settings: Settings = Depends(get_settings)) -> EmbeddingProvider:
    provider = _embedding_provider_cache.get(settings.embedding_model)
    if provider is None:
        provider = BGEEmbeddingProvider(
            settings.embedding_model, batch_size=settings.embedding_batch_size
        )
        _embedding_provider_cache[settings.embedding_model] = provider
    return provider


def get_dense_retriever(
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(_get_connection),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> DenseRetriever:
    chunks = ChunkRepository(conn).list_all()
    store = FaissIndexStore(index_dir=Path(settings.index_dir))

    # Convenience index lifecycle for the debug endpoint: build the index if
    # it has never been built, and rebuild it if it is stale relative to
    # the current chunk set. This is index bookkeeping, not a fallback
    # between retrieval modes — the mode the caller asked for still runs
    # against a consistent index either way.
    if not store.exists():
        store = FaissIndexStore.build(
            chunks,
            embedding_provider,
            settings.index_dir,
            settings.chunk_target_tokens,
            settings.chunk_overlap_tokens,
        )
    else:
        store = store.load()
        if store.is_stale(chunks):
            store = FaissIndexStore.build(
                chunks,
                embedding_provider,
                settings.index_dir,
                settings.chunk_target_tokens,
                settings.chunk_overlap_tokens,
            )

    chunks_by_id = {c.id: c for c in chunks}
    return DenseRetriever(store, embedding_provider, chunks_by_id)


def get_hyde_expander(settings: Settings = Depends(get_settings)) -> QueryExpander | None:
    """`None` when HyDE is disabled by configuration — `RetrievalService`
    then raises an explicit `HyDEUnavailableError` if a HyDE-dependent mode
    is requested, rather than silently downgrading to a non-HyDE mode."""
    if not settings.hyde_enabled:
        return None
    client = OllamaClient(
        settings.ollama_base_url, settings.hyde_model, settings.hyde_timeout_seconds
    )
    return HyDEExpander(client, settings.hyde_max_tokens, settings.hyde_temperature)


def get_reranker(settings: Settings = Depends(get_settings)) -> Reranker:
    reranker = _reranker_cache.get(settings.reranker_model)
    if reranker is None:
        reranker = CrossEncoderReranker(settings.reranker_model)
        _reranker_cache[settings.reranker_model] = reranker
    return reranker


def get_retrieval_service(
    settings: Settings = Depends(get_settings),
    bm25: BM25Retriever = Depends(get_bm25_retriever),
    dense: DenseRetriever = Depends(get_dense_retriever),
    hyde: QueryExpander | None = Depends(get_hyde_expander),
    reranker: Reranker = Depends(get_reranker),
) -> RetrievalService:
    config = RetrievalServiceConfig(
        bm25_top_k=settings.bm25_top_k,
        dense_top_k=settings.dense_top_k,
        rrf_k=settings.rrf_k,
        rrf_candidate_k=settings.rrf_candidate_k,
        rerank_candidate_k=settings.rerank_candidate_k,
        final_top_k=settings.final_top_k,
    )
    return RetrievalService(bm25, dense, hyde, RRFFusion(k=settings.rrf_k), reranker, config)


_ERROR_STATUS: dict[type[RetrievalError], int] = {
    EmptyQueryError: 400,
    InvalidModeError: 400,
    NoIndexedChunksError: 409,
    HyDEUnavailableError: 503,
    EmbeddingModelError: 503,
    RerankerModelError: 503,
}


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    service: RetrievalService = Depends(get_retrieval_service),
) -> SearchResponse:
    try:
        results, trace = service.retrieve(request.query, request.mode, top_k=request.top_k)
    except RetrievalError as exc:
        status_code = next(
            (code for error_type, code in _ERROR_STATUS.items() if isinstance(exc, error_type)),
            500,
        )
        raise HTTPException(status_code=status_code, detail=exc.message) from exc

    return SearchResponse(
        query=request.query,
        mode=request.mode,
        request_id=trace.request_id,
        hyde_query=trace.hyde_query,
        results=[
            SearchResultItem(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                rank=r.rank,
                score=r.score,
                retrieval_source=r.retrieval_source.value,
                page=r.page,
                section=r.section,
                content_preview=preview(r.content),
                bm25_rank=r.bm25_rank,
                bm25_score=r.bm25_score,
                dense_rank=r.dense_rank,
                dense_score=r.dense_score,
                rrf_score=r.rrf_score,
                rerank_score=r.rerank_score,
                chunk_type=r.metadata.get("chunk_type"),
            )
            for r in results
        ],
        timing=TimingResponse(
            query_embedding_ms=trace.timings.query_embedding_ms,
            bm25_ms=trace.timings.bm25_ms,
            faiss_ms=trace.timings.faiss_ms,
            hyde_ms=trace.timings.hyde_ms,
            rrf_ms=trace.timings.rrf_ms,
            reranking_ms=trace.timings.reranking_ms,
            total_ms=trace.timings.total_ms,
        ),
    )

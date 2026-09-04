"""RetrievalService: orchestrates retrieval modes.

Coordinates `BM25Retriever`, `DenseRetriever`, `HyDEExpander`, `RRFFusion`,
and `CrossEncoderReranker` — it does **not** implement any retrieval
algorithm itself (spec: "it should NOT itself implement the algorithms,
just orchestrate"). Every mode is independently selectable via the `mode`
argument; nothing here branches on hidden state or falls back between
modes unless the caller explicitly chose a HyDE-enabled mode.
"""

from __future__ import annotations

import time
import unicodedata
import uuid
from dataclasses import dataclass

from app.retrieval.errors import (
    EmptyQueryError,
    HyDEUnavailableError,
    InvalidModeError,
    InvalidQueryError,
    InvalidTopKError,
    QueryTooLongError,
)
from app.retrieval.interfaces import (
    FusedCandidate,
    FusionStrategy,
    QueryExpander,
    RerankedCandidate,
    Reranker,
    Retriever,
)
from app.retrieval.models import (
    RetrievalCandidate,
    RetrievalMode,
    RetrievalResult,
    RetrievalSource,
    RetrievalTrace,
    TimingBreakdown,
)


@dataclass
class RetrievalServiceConfig:
    bm25_top_k: int
    dense_top_k: int
    rrf_k: int
    rrf_candidate_k: int
    rerank_candidate_k: int
    final_top_k: int
    # Phase 8 resource limits (spec section 8G/8T). Defaulted so every
    # pre-existing construction site (benchmarking, experiment scripts,
    # tests) keeps working unchanged; only `app.api.retrieval` wires these
    # from `Settings.security_max_query_length`/`security_max_top_k`.
    max_query_length: int = 4000
    max_top_k: int = 100


def _candidate_to_result(candidate: RetrievalCandidate, source: RetrievalSource) -> RetrievalResult:
    result = RetrievalResult(
        chunk_id=candidate.chunk_id,
        document_id=candidate.document_id,
        content=candidate.content,
        score=candidate.score,
        rank=candidate.rank,
        retrieval_source=source,
        page=candidate.page,
        section=candidate.section,
        parent_id=candidate.parent_id,
        metadata=candidate.metadata,
    )
    if source == RetrievalSource.BM25:
        result.bm25_rank = candidate.rank
        result.bm25_score = candidate.score
    elif source == RetrievalSource.DENSE:
        result.dense_rank = candidate.rank
        result.dense_score = candidate.score
    return result


def _fused_to_result(candidate: FusedCandidate) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=candidate.chunk_id,
        document_id=candidate.document_id,
        content=candidate.content,
        score=candidate.fused_score,
        rank=candidate.rank,
        retrieval_source=RetrievalSource.RRF,
        page=candidate.page,
        section=candidate.section,
        parent_id=candidate.parent_id,
        metadata=candidate.metadata,
        bm25_rank=candidate.source_ranks.get("bm25"),
        bm25_score=candidate.source_scores.get("bm25"),
        dense_rank=candidate.source_ranks.get("dense"),
        dense_score=candidate.source_scores.get("dense"),
        rrf_score=candidate.fused_score,
    )


def _reranked_to_result(candidate: RerankedCandidate) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=candidate.chunk_id,
        document_id=candidate.document_id,
        content=candidate.content,
        score=candidate.rerank_score,
        rank=candidate.rank,
        retrieval_source=RetrievalSource.RERANKER,
        page=candidate.page,
        section=candidate.section,
        parent_id=candidate.parent_id,
        metadata=candidate.metadata,
        bm25_rank=candidate.source_ranks.get("bm25"),
        bm25_score=candidate.source_scores.get("bm25"),
        dense_rank=candidate.source_ranks.get("dense"),
        dense_score=candidate.source_scores.get("dense"),
        rrf_score=candidate.fused_score,
        rerank_score=candidate.rerank_score,
    )


def _ms_since(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


_ALLOWED_CONTROL_CHARS = frozenset({"\t", "\n", "\r"})


def _contains_disallowed_control_chars(text: str) -> bool:
    """True if `text` contains a Unicode control character (category "Cc")
    other than tab/newline/carriage-return. A legitimate question never
    needs these; allowing them through risks log/terminal injection
    downstream (spec section 8G/8Q) since queries are logged verbatim."""
    return any(
        unicodedata.category(ch) == "Cc" and ch not in _ALLOWED_CONTROL_CHARS for ch in text
    )


class RetrievalService:
    def __init__(
        self,
        bm25_retriever: Retriever,
        dense_retriever: Retriever,
        hyde_expander: QueryExpander | None,
        fusion: FusionStrategy,
        reranker: Reranker,
        config: RetrievalServiceConfig,
    ) -> None:
        self._bm25 = bm25_retriever
        self._dense = dense_retriever
        self._hyde = hyde_expander
        self._fusion = fusion
        self._reranker = reranker
        self._config = config

    def retrieve(
        self,
        query: str,
        mode: RetrievalMode | str,
        top_k: int | None = None,
        request_id: str | None = None,
    ) -> tuple[list[RetrievalResult], RetrievalTrace]:
        if not query or not query.strip():
            raise EmptyQueryError("Query must not be empty.")

        if len(query) > self._config.max_query_length:
            raise QueryTooLongError(
                f"Query exceeds the {self._config.max_query_length}-character limit."
            )

        if _contains_disallowed_control_chars(query):
            raise InvalidQueryError("Query contains unsupported control characters.")

        if isinstance(mode, str):
            try:
                mode = RetrievalMode(mode)
            except ValueError as exc:
                raise InvalidModeError(f"Unrecognized retrieval mode: {mode!r}") from exc

        if top_k is not None and not (1 <= top_k <= self._config.max_top_k):
            raise InvalidTopKError(
                f"top_k must be between 1 and {self._config.max_top_k}."
            )

        request_id = request_id or uuid.uuid4().hex
        resolved_top_k = top_k if top_k is not None else self._config.final_top_k

        trace = RetrievalTrace(request_id=request_id, query=query, mode=mode)
        timings = TimingBreakdown()
        total_start = time.perf_counter()

        if mode == RetrievalMode.BM25:
            results = self._run_bm25(query, resolved_top_k, trace, timings)
        elif mode == RetrievalMode.DENSE:
            results = self._run_dense(query, resolved_top_k, trace, timings)
        elif mode == RetrievalMode.DENSE_HYDE:
            results = self._run_dense_hyde(query, resolved_top_k, trace, timings)
        elif mode == RetrievalMode.HYBRID_RRF:
            results = self._run_hybrid_rrf(query, resolved_top_k, trace, timings, use_hyde=False)
        elif mode == RetrievalMode.HYBRID_RRF_HYDE:
            results = self._run_hybrid_rrf(query, resolved_top_k, trace, timings, use_hyde=True)
        elif mode == RetrievalMode.FULL_BASELINE:
            results = self._run_full_baseline(query, resolved_top_k, trace, timings)
        else:  # pragma: no cover - RetrievalMode is exhaustive above
            raise InvalidModeError(f"Unrecognized retrieval mode: {mode!r}")

        timings.total_ms = _ms_since(total_start)
        trace.timings = timings
        return results, trace

    def _run_bm25(
        self, query: str, top_k: int, trace: RetrievalTrace, timings: TimingBreakdown
    ) -> list[RetrievalResult]:
        start = time.perf_counter()
        candidates = self._bm25.retrieve(query, top_k)
        timings.bm25_ms = _ms_since(start)
        trace.bm25_candidates = candidates
        return [_candidate_to_result(c, RetrievalSource.BM25) for c in candidates]

    def _run_dense(
        self, query: str, top_k: int, trace: RetrievalTrace, timings: TimingBreakdown
    ) -> list[RetrievalResult]:
        start = time.perf_counter()
        candidates = self._dense.retrieve(query, top_k)
        timings.faiss_ms = _ms_since(start)
        trace.dense_candidates = candidates
        return [_candidate_to_result(c, RetrievalSource.DENSE) for c in candidates]

    def _expand_with_hyde(self, query: str, trace: RetrievalTrace, timings: TimingBreakdown) -> str:
        if self._hyde is None:
            raise HyDEUnavailableError("HyDE was requested but no HyDE provider is configured.")
        start = time.perf_counter()
        expansion = self._hyde.expand(query)
        timings.hyde_ms = _ms_since(start)
        trace.hyde_query = expansion.expanded_text
        trace.hyde_model = expansion.model
        trace.hyde_generation_params = expansion.generation_params
        return expansion.expanded_text

    def _run_dense_hyde(
        self, query: str, top_k: int, trace: RetrievalTrace, timings: TimingBreakdown
    ) -> list[RetrievalResult]:
        hyde_text = self._expand_with_hyde(query, trace, timings)
        start = time.perf_counter()
        candidates = self._dense.retrieve(hyde_text, top_k)
        timings.faiss_ms = _ms_since(start)
        trace.dense_candidates = candidates
        return [_candidate_to_result(c, RetrievalSource.DENSE) for c in candidates]

    def _run_hybrid_rrf(
        self,
        query: str,
        top_k: int,
        trace: RetrievalTrace,
        timings: TimingBreakdown,
        use_hyde: bool,
    ) -> list[RetrievalResult]:
        fused = self._fused_candidates(query, trace, timings, use_hyde)
        top = fused[:top_k]
        trace.rrf_candidates = [_fused_to_result(c) for c in fused[: self._config.rrf_candidate_k]]
        return [_fused_to_result(c) for c in top]

    def _run_full_baseline(
        self, query: str, top_k: int, trace: RetrievalTrace, timings: TimingBreakdown
    ) -> list[RetrievalResult]:
        fused = self._fused_candidates(query, trace, timings, use_hyde=True)
        pool = fused[: self._config.rerank_candidate_k]
        trace.rrf_candidates = [_fused_to_result(c) for c in pool]

        start = time.perf_counter()
        reranked = self._reranker.rerank(query, pool, top_k=top_k)
        timings.reranking_ms = _ms_since(start)
        trace.rerank_candidates = [_reranked_to_result(c) for c in reranked]
        return [_reranked_to_result(c) for c in reranked]

    def _fused_candidates(
        self, query: str, trace: RetrievalTrace, timings: TimingBreakdown, use_hyde: bool
    ) -> list[FusedCandidate]:
        dense_query = self._expand_with_hyde(query, trace, timings) if use_hyde else query

        # BM25 always receives the original `query`; `dense_query` is either
        # that same original query or HyDE text, decided above. Each stage
        # is timed individually for the trace, so `HybridRetriever.retrieve`
        # (which times nothing) is not used directly here — it remains the
        # independently testable/usable component for callers that don't
        # need per-stage timings (see hybrid.py, test_hybrid.py).
        bm25_start = time.perf_counter()
        bm25_candidates = self._bm25.retrieve(query, self._config.bm25_top_k)
        timings.bm25_ms = _ms_since(bm25_start)
        trace.bm25_candidates = bm25_candidates

        dense_start = time.perf_counter()
        dense_candidates = self._dense.retrieve(dense_query, self._config.dense_top_k)
        timings.faiss_ms = _ms_since(dense_start)
        trace.dense_candidates = dense_candidates

        rrf_start = time.perf_counter()
        fused = self._fusion.fuse({"bm25": bm25_candidates, "dense": dense_candidates})
        timings.rrf_ms = _ms_since(rrf_start)
        return fused

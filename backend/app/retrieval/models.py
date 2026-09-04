"""Retrieval domain model (Phase 2).

Independent of any specific library (rank_bm25, faiss, sentence-transformers)
the same way `app.ingestion.models` is independent of Docling — see
docs/decisions/ADR-004-model-agnostic-interfaces.md. Downstream code (the
API layer, the evaluation harness) depends only on these dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RetrievalSource(StrEnum):
    """Which stage of the pipeline produced a given result.

    Kept distinct from a generic "score" field because a hybrid/rrf/reranker
    result carries more than one number (see `RetrievalResult` below) and
    collapsing provenance into a single field would make it ambiguous which
    stage a given rank/score actually came from.
    """

    BM25 = "bm25"
    DENSE = "dense"
    HYBRID = "hybrid"
    RRF = "rrf"
    RERANKER = "reranker"


class RetrievalMode(StrEnum):
    """Selectable end-to-end retrieval strategies.

    Selected by config/API/function argument — never by editing source, per
    the Phase 2 spec's "Retrieval Modes" section.
    """

    BM25 = "bm25"
    DENSE = "dense"
    DENSE_HYDE = "dense_hyde"
    HYBRID_RRF = "hybrid_rrf"
    HYBRID_RRF_HYDE = "hybrid_rrf_hyde"
    FULL_BASELINE = "full_baseline"


@dataclass
class RetrievalQuery:
    """A single retrieval request, already normalized (see errors.py)."""

    text: str
    mode: RetrievalMode
    top_k: int
    request_id: str


@dataclass
class RetrievalCandidate:
    """One retriever's view of one chunk: a rank and a source-native score.

    Intentionally minimal — this is the unit that BM25Retriever/
    DenseRetriever produce, before fusion/reranking add more information.
    """

    chunk_id: str
    document_id: str
    content: str
    rank: int
    score: float
    page: int | None = None
    section: str | None = None
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """A single ranked item in a `RetrievalService.retrieve(...)` response.

    Deliberately carries *multiple* named scores rather than one ambiguous
    `score` field, so a hybrid/rrf/reranked result preserves how each stage
    ranked it (per the Phase 2 spec: "For hybrid results preserve component
    scores/ranks. Don't overload one ambiguous score field.").

    - `score` / `rank`: the *final* score/rank for this result at the
      pipeline stage named by `retrieval_source` (e.g. the reranker's score
      and rank for a `full_baseline` result).
    - `bm25_rank` / `bm25_score`, `dense_rank` / `dense_score`: preserved
      component ranks/scores when this result passed through BM25 and/or
      dense retrieval, regardless of whether it was ultimately reranked.
    - `rrf_score`: the fused RRF score, when RRF ran.
    """

    chunk_id: str
    document_id: str
    content: str
    score: float
    rank: int
    retrieval_source: RetrievalSource
    page: int | None = None
    section: str | None = None
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    bm25_rank: int | None = None
    bm25_score: float | None = None
    dense_rank: int | None = None
    dense_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


@dataclass
class TimingBreakdown:
    """Per-stage wall-clock timings in milliseconds. `None` = stage skipped."""

    query_embedding_ms: float | None = None
    bm25_ms: float | None = None
    faiss_ms: float | None = None
    hyde_ms: float | None = None
    rrf_ms: float | None = None
    reranking_ms: float | None = None
    total_ms: float = 0.0


@dataclass
class RetrievalTrace:
    """Full observability record for one `retrieve()` call.

    Built during retrieval, not reconstructed after the fact — available
    programmatically (the evaluation harness reads it directly) as well as
    being loggable. Content is kept to ids/ranks/scores; full chunk text is
    intentionally not duplicated here (the caller already has it via
    `RetrievalResult.content`).
    """

    request_id: str
    query: str
    mode: RetrievalMode
    hyde_query: str | None = None
    hyde_model: str | None = None
    hyde_generation_params: dict[str, Any] = field(default_factory=dict)

    bm25_candidates: list[RetrievalCandidate] = field(default_factory=list)
    dense_candidates: list[RetrievalCandidate] = field(default_factory=list)
    rrf_candidates: list[RetrievalResult] = field(default_factory=list)
    rerank_candidates: list[RetrievalResult] = field(default_factory=list)

    timings: TimingBreakdown = field(default_factory=TimingBreakdown)

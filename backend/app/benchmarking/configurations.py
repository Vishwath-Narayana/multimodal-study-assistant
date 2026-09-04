"""Named retrieval configurations for the Phase 7C/7F evaluation (real,
measured — no HyDE, no generation; see `hyde_pipeline_validation.py` for
the separately-labeled mocked-HyDE pipeline check).

Configs B/E use `RetrievalService` directly (unchanged Phase 2 code). "D"
(simple, non-RRF score combination) and "H" (hybrid+RRF+reranker *without*
HyDE) are not expressible through `RetrievalService` as-is — `full_baseline`
hardcodes HyDE — so they are composed here, for evaluation only, directly
from the same real `BM25Retriever`/`DenseRetriever`/`RRFFusion`/
`CrossEncoderReranker` components `RetrievalService` itself uses. This adds
no new retrieval algorithm; it only recombines existing ones in an order
the production service doesn't happen to expose.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.benchmarking.wiring import RealStack
from app.retrieval.models import RetrievalMode

CANDIDATE_POOL_K = 20


@dataclass
class ConfigResult:
    chunk_ids: list[str]
    latency_ms: float


def simple_score_fusion(bm25_candidates: list, dense_candidates: list, top_k: int) -> list[str]:
    """ "Simple score fusion" baseline for the 7F.4 RRF ablation: min-max
    normalize each source's native scores independently (they are not on
    comparable scales), then sum. Distinct from RRF, which never looks at
    scores at all, only ranks. Deterministic tie-break: (-score, chunk_id).
    """

    def normalize(candidates: list) -> dict[str, float]:
        if not candidates:
            return {}
        scores = [c.score for c in candidates]
        lo, hi = min(scores), max(scores)
        span = hi - lo
        if span == 0:
            return {c.chunk_id: 1.0 for c in candidates}
        return {c.chunk_id: (c.score - lo) / span for c in candidates}

    bm25_norm = normalize(bm25_candidates)
    dense_norm = normalize(dense_candidates)
    all_ids = set(bm25_norm) | set(dense_norm)
    combined = {cid: bm25_norm.get(cid, 0.0) + dense_norm.get(cid, 0.0) for cid in all_ids}
    ordered = sorted(combined.items(), key=lambda item: (-item[1], item[0]))
    return [chunk_id for chunk_id, _ in ordered[:top_k]]


def run_bm25(stack: RealStack, query: str, top_k: int) -> ConfigResult:
    start = time.perf_counter()
    results, _ = stack.service.retrieve(query, RetrievalMode.BM25, top_k=top_k)
    return ConfigResult([r.chunk_id for r in results], (time.perf_counter() - start) * 1000)


def run_dense(stack: RealStack, query: str, top_k: int) -> ConfigResult:
    start = time.perf_counter()
    results, _ = stack.service.retrieve(query, RetrievalMode.DENSE, top_k=top_k)
    return ConfigResult([r.chunk_id for r in results], (time.perf_counter() - start) * 1000)


def run_simple_combination(stack: RealStack, query: str, top_k: int) -> ConfigResult:
    start = time.perf_counter()
    bm25_candidates = stack.bm25.retrieve(query, CANDIDATE_POOL_K)
    dense_candidates = stack.dense.retrieve(query, CANDIDATE_POOL_K)
    chunk_ids = simple_score_fusion(bm25_candidates, dense_candidates, top_k)
    return ConfigResult(chunk_ids, (time.perf_counter() - start) * 1000)


def run_hybrid_rrf(stack: RealStack, query: str, top_k: int) -> ConfigResult:
    start = time.perf_counter()
    results, _ = stack.service.retrieve(query, RetrievalMode.HYBRID_RRF, top_k=top_k)
    return ConfigResult([r.chunk_id for r in results], (time.perf_counter() - start) * 1000)


def run_hybrid_rrf_reranked(stack: RealStack, query: str, top_k: int) -> ConfigResult:
    """Hybrid + RRF + cross-encoder reranker, no HyDE (Phase 7C config H)."""
    start = time.perf_counter()
    bm25_candidates = stack.bm25.retrieve(query, CANDIDATE_POOL_K)
    dense_candidates = stack.dense.retrieve(query, CANDIDATE_POOL_K)
    fused = stack.fusion.fuse({"bm25": bm25_candidates, "dense": dense_candidates})
    pool = fused[:CANDIDATE_POOL_K]
    reranked = stack.reranker.rerank(query, pool, top_k=top_k)
    return ConfigResult([r.chunk_id for r in reranked], (time.perf_counter() - start) * 1000)


REAL_CONFIGS = {
    "A_bm25": run_bm25,
    "B_dense": run_dense,
    "D_bm25_dense_simple_fusion": run_simple_combination,
    "E_hybrid_rrf": run_hybrid_rrf,
    "H_hybrid_rrf_reranked": run_hybrid_rrf_reranked,
}

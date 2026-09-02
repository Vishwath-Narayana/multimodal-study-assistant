"""HybridRetriever: coordinates BM25 + dense retrieval + fusion.

Deliberately thin — it does not implement BM25, dense search, or RRF math
itself, only wires the two `Retriever`s and a `FusionStrategy` together.
`bm25_query` and `dense_query` are passed in *separately* by the caller
(`RetrievalService`) precisely so BM25 can receive the original query while
dense receives either the original query or HyDE text — this class has no
opinion on which; it never inspects or compares the two strings.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.interfaces import FusedCandidate, FusionStrategy, Retriever
from app.retrieval.models import RetrievalCandidate


@dataclass
class HybridRetrievalOutput:
    bm25_candidates: list[RetrievalCandidate]
    dense_candidates: list[RetrievalCandidate]
    fused_candidates: list[FusedCandidate]


class HybridRetriever:
    def __init__(self, bm25: Retriever, dense: Retriever, fusion: FusionStrategy) -> None:
        self._bm25 = bm25
        self._dense = dense
        self._fusion = fusion

    def retrieve(
        self,
        bm25_query: str,
        dense_query: str,
        bm25_top_k: int,
        dense_top_k: int,
    ) -> HybridRetrievalOutput:
        bm25_candidates = self._bm25.retrieve(bm25_query, bm25_top_k)
        dense_candidates = self._dense.retrieve(dense_query, dense_top_k)
        fused = self._fusion.fuse({"bm25": bm25_candidates, "dense": dense_candidates})
        return HybridRetrievalOutput(
            bm25_candidates=bm25_candidates,
            dense_candidates=dense_candidates,
            fused_candidates=fused,
        )


def inspect_union(
    bm25_candidates: list[RetrievalCandidate],
    dense_candidates: list[RetrievalCandidate],
) -> list[RetrievalCandidate]:
    """Engineering inspection mode: a simple union/dedup of the two raw
    candidate sets, in encounter order (BM25 first, then any dense
    candidates not already seen). This is **not** a scientifically
    meaningful weighted-score final ranking — it exists only so overlap and
    differences between the two retrievers can be observed directly,
    without RRF's rank-based fusion in the way. Use `RRFFusion` for any
    result that is actually reported as a ranking.
    """
    seen: set[str] = set()
    union: list[RetrievalCandidate] = []
    for candidate in [*bm25_candidates, *dense_candidates]:
        if candidate.chunk_id in seen:
            continue
        seen.add(candidate.chunk_id)
        union.append(candidate)
    return union

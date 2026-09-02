"""Reciprocal Rank Fusion.

`RRF_score(d) = sum over lists i containing d of 1 / (k + rank_i(d))`

Operates purely on **ranks** — it never looks at BM25/dense scores, which
are not on comparable scales (spec: "Do not invent score normalization
before RRF — operate on ranks"). `k` defaults to 60 (the standard RRF
constant, and EduRAG's baseline value).
"""

from __future__ import annotations

from app.retrieval.interfaces import FusedCandidate, FusionStrategy
from app.retrieval.models import RetrievalCandidate


class RRFFusion(FusionStrategy):
    def __init__(self, k: int = 60) -> None:
        self._k = k

    def fuse(self, ranked_lists: dict[str, list[RetrievalCandidate]]) -> list[FusedCandidate]:
        # source_ranks[chunk_id][source] = rank; keep one representative
        # candidate (content/metadata) per chunk id, preferring whichever
        # source we see it in first (both should carry identical chunk
        # metadata since they come from the same underlying chunk).
        by_chunk: dict[str, RetrievalCandidate] = {}
        source_ranks: dict[str, dict[str, int]] = {}
        source_scores: dict[str, dict[str, float]] = {}

        for source, candidates in ranked_lists.items():
            for candidate in candidates:
                by_chunk.setdefault(candidate.chunk_id, candidate)
                source_ranks.setdefault(candidate.chunk_id, {})[source] = candidate.rank
                source_scores.setdefault(candidate.chunk_id, {})[source] = candidate.score

        fused_scores: dict[str, float] = {
            chunk_id: sum(1.0 / (self._k + rank) for rank in ranks.values())
            for chunk_id, ranks in source_ranks.items()
        }

        # Deterministic tie-breaking: sort by (-fused_score, chunk_id).
        ordered = sorted(fused_scores.items(), key=lambda item: (-item[1], item[0]))

        results: list[FusedCandidate] = []
        for rank, (chunk_id, fused_score) in enumerate(ordered, start=1):
            candidate = by_chunk[chunk_id]
            results.append(
                FusedCandidate(
                    chunk_id=chunk_id,
                    document_id=candidate.document_id,
                    content=candidate.content,
                    fused_score=fused_score,
                    rank=rank,
                    page=candidate.page,
                    section=candidate.section,
                    parent_id=candidate.parent_id,
                    metadata=candidate.metadata,
                    source_ranks=source_ranks[chunk_id],
                    source_scores=source_scores[chunk_id],
                )
            )
        return results

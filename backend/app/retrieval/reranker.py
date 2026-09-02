"""Cross-encoder reranking.

`CrossEncoderReranker` scores `(query, chunk content)` pairs with
`cross-encoder/ms-marco-MiniLM-L-6-v2` (the Phase 2 baseline reranker) and
returns the pool re-sorted by that score. Loaded once, reused across calls
(same lifecycle discipline as `BGEEmbeddingProvider`).
"""

from __future__ import annotations

from app.retrieval.errors import RerankerModelError
from app.retrieval.interfaces import FusedCandidate, Reranker, RerankedCandidate


class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None  # lazy-loaded once, then cached

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        except Exception as exc:  # noqa: BLE001
            raise RerankerModelError(
                f"Failed to load reranker model '{self._model_name}': {exc}"
            ) from exc

    @property
    def model_id(self) -> str:
        return self._model_name

    def rerank(
        self, query: str, candidates: list[FusedCandidate], top_k: int
    ) -> list[RerankedCandidate]:
        if not candidates or top_k <= 0:
            return []
        self._ensure_loaded()
        assert self._model is not None

        pairs = [(query, c.content) for c in candidates]
        try:
            scores = self._model.predict(pairs)
        except Exception as exc:  # noqa: BLE001
            raise RerankerModelError(f"Reranker model failed to score candidates: {exc}") from exc

        # Deterministic tie-breaking: sort by (-score, chunk_id), same
        # convention as BM25/RRF.
        order = sorted(
            range(len(candidates)),
            key=lambda i: (-float(scores[i]), candidates[i].chunk_id),
        )[:top_k]

        results: list[RerankedCandidate] = []
        for rank, idx in enumerate(order, start=1):
            candidate = candidates[idx]
            results.append(
                RerankedCandidate(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    content=candidate.content,
                    rerank_score=float(scores[idx]),
                    rank=rank,
                    page=candidate.page,
                    section=candidate.section,
                    parent_id=candidate.parent_id,
                    metadata=candidate.metadata,
                    fused_score=candidate.fused_score,
                    source_ranks=candidate.source_ranks,
                    source_scores=candidate.source_scores,
                )
            )
        return results

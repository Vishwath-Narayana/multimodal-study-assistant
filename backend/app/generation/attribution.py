"""Deterministic chunk attribution (EduRAG-inspired).

Baseline methodology (EduRAG, see module docstring in
docs/architecture/generation.md for the full citation):

    attribution_score = 0.7 x cross-encoder relevance + 0.3 x lexical overlap

This implementation:

- **Cross-encoder relevance**: the chunk's `rerank_score` from Phase 2
  (`RetrievalResult.rerank_score`), when available. Cross-encoder scores are
  unbounded logit-like values, not already in [0, 1], so they are min-max
  normalized *across the evidence set for this request* before combining —
  the same normalization approach used nowhere else in this codebase, so it
  is spelled out here rather than assumed. When no evidence item has a
  `rerank_score` (e.g. bm25/dense/hybrid_rrf modes, which never run the
  cross-encoder), the final `RetrievalResult.score` for that mode is used
  as the relevance signal instead, min-max normalized the same way — this
  keeps attribution computable in every retrieval mode while still
  reflecting *that mode's* notion of relevance rather than inventing a
  different metric.
- **Lexical overlap**: Jaccard similarity between the answer's tokens and
  the chunk's tokens (same tokenizer as BM25 and sufficiency,
  `app.retrieval.tokenizer.tokenize`).

Given the same answer text and the same evidence list (same scores, same
content), this always produces the same attribution scores and ranking —
ties are broken by `chunk_id` for full determinism.
"""

from __future__ import annotations

from app.generation.citations import strip_citation_markers
from app.generation.interfaces import ChunkAttributor
from app.generation.models import AttributionScore
from app.retrieval.models import RetrievalResult
from app.retrieval.tokenizer import tokenize

RELEVANCE_WEIGHT = 0.7
LEXICAL_WEIGHT = 0.3


def _jaccard(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


def _min_max_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        # All candidates equally (ir)relevant by this signal — attribution
        # then rests entirely on lexical overlap for this evidence set.
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


class DeterministicChunkAttributor(ChunkAttributor):
    def attribute(self, answer: str, evidence: list[RetrievalResult]) -> list[AttributionScore]:
        if not evidence:
            return []

        answer_text = strip_citation_markers(answer)
        answer_tokens = set(tokenize(answer_text))

        raw_relevance = [
            item.rerank_score if item.rerank_score is not None else item.score
            for item in evidence
        ]
        normalized_relevance = _min_max_normalize(raw_relevance)

        scored: list[tuple[str, float]] = []
        for item, relevance in zip(evidence, normalized_relevance, strict=True):
            lexical_overlap = _jaccard(answer_tokens, set(tokenize(item.content)))
            score = RELEVANCE_WEIGHT * relevance + LEXICAL_WEIGHT * lexical_overlap
            scored.append((item.chunk_id, score))

        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return [
            AttributionScore(chunk_id=chunk_id, attribution_score=score, rank=rank)
            for rank, (chunk_id, score) in enumerate(scored, start=1)
        ]

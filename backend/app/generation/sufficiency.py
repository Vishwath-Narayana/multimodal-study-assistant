"""Evidence sufficiency / abstention gate.

Runs *before* generation so the system never blindly generates an answer
for every query (spec section 8). This is a documented heuristic, not a
validated confidence model — see docs/architecture/generation.md
"Limitations" for what it does and does not catch.

Design: retrieval scores are not directly comparable across modes (BM25's
score is an unbounded lexical statistic, a cross-encoder's score is an
unbounded logit-like value, RRF's score is a small fused reciprocal-rank
sum) so a single absolute score threshold across all six retrieval modes
would be meaningless. Instead this checker combines:

1. **Chunk count** — was anything retrieved at all.
2. **Lexical overlap** — Jaccard similarity between the query's tokens and
   the best-matching chunk's tokens (using the same tokenizer as BM25,
   `app.retrieval.tokenizer.tokenize`, so this stays comparable across every
   retrieval mode, including modes with no cross-encoder score at all).
3. **Reranker score** — only used as a *positive* signal when a cross-
   encoder score is present (`retrieval_source == RERANKER` / full_baseline
   mode), since `ms-marco-MiniLM`-style cross-encoders are the one score in
   this pipeline whose sign is a meaningful, comparable relevance signal
   (roughly: positive = relevant, negative = irrelevant).

Evidence is judged sufficient if there is at least the configured minimum
number of chunks AND (the top chunk's lexical overlap clears the configured
threshold OR its reranker score clears the configured threshold, when
available). This intentionally does not fold in contradiction detection —
conflicting evidence can still be sufficient to attempt an answer (the
contradiction checker's job is to surface the disagreement in the response,
not to force an abstention).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.generation.interfaces import EvidenceSufficiencyChecker
from app.generation.models import SufficiencyResult
from app.retrieval.models import RetrievalResult
from app.retrieval.tokenizer import tokenize


def _jaccard(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


@dataclass
class SufficiencyConfig:
    min_chunks: int
    min_lexical_overlap: float
    min_reranker_score: float


class HeuristicSufficiencyChecker(EvidenceSufficiencyChecker):
    def __init__(self, config: SufficiencyConfig) -> None:
        self._config = config

    def check(self, query: str, evidence: list[RetrievalResult]) -> SufficiencyResult:
        if len(evidence) < self._config.min_chunks:
            return SufficiencyResult(
                sufficient=False,
                reason=(
                    f"Only {len(evidence)} evidence chunk(s) were retrieved; "
                    f"at least {self._config.min_chunks} are required."
                ),
                signals={
                    "chunk_count": len(evidence),
                    "min_chunks": self._config.min_chunks,
                },
            )

        query_tokens = set(tokenize(query))
        overlaps = [_jaccard(query_tokens, set(tokenize(item.content))) for item in evidence]
        best_overlap = max(overlaps) if overlaps else 0.0

        top = evidence[0]
        reranker_score = top.rerank_score
        reranker_signal_ok = (
            reranker_score is not None and reranker_score >= self._config.min_reranker_score
        )
        lexical_signal_ok = best_overlap >= self._config.min_lexical_overlap

        signals = {
            "chunk_count": len(evidence),
            "best_lexical_overlap": best_overlap,
            "min_lexical_overlap": self._config.min_lexical_overlap,
            "top_reranker_score": reranker_score,
            "min_reranker_score": self._config.min_reranker_score,
        }

        if lexical_signal_ok or reranker_signal_ok:
            return SufficiencyResult(
                sufficient=True, reason="Evidence passed sufficiency checks.", signals=signals
            )

        return SufficiencyResult(
            sufficient=False,
            reason=(
                "Retrieved evidence does not appear to address the question closely enough "
                f"(best lexical overlap {best_overlap:.3f} < {self._config.min_lexical_overlap}"
                + (
                    f", reranker score {reranker_score:.3f} < {self._config.min_reranker_score}"
                    if reranker_score is not None
                    else ", no reranker score available"
                )
                + ")."
            ),
            signals=signals,
        )

from __future__ import annotations

from app.retrieval.interfaces import FusedCandidate
from app.retrieval.reranker import CrossEncoderReranker


class _FakeCrossEncoderModel:
    """Deterministic mocked cross-encoder: score = length of chunk content
    that overlaps (as a set of words) with the query, so ranking is
    predictable without loading any real model."""

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        scores = []
        for query, content in pairs:
            query_words = set(query.lower().split())
            content_words = set(content.lower().split())
            scores.append(float(len(query_words & content_words)))
        return scores


def _candidate(chunk_id: str, content: str, fused_score: float = 0.5) -> FusedCandidate:
    return FusedCandidate(
        chunk_id=chunk_id,
        document_id="doc-1",
        content=content,
        fused_score=fused_score,
        rank=1,
        source_ranks={"bm25": 1},
        source_scores={"bm25": 1.0},
    )


def _reranker_with_fake_model() -> CrossEncoderReranker:
    reranker = CrossEncoderReranker("cross-encoder/ms-marco-MiniLM-L-6-v2")
    reranker._model = _FakeCrossEncoderModel()  # bypass real model load
    return reranker


def test_reorders_candidates_by_score() -> None:
    candidates = [
        _candidate("low", "irrelevant sentence about nothing"),
        _candidate("high", "photosynthesis converts light energy"),
    ]
    reranker = _reranker_with_fake_model()
    results = reranker.rerank("photosynthesis light energy", candidates, top_k=2)
    assert [r.chunk_id for r in results] == ["high", "low"]
    assert results[0].rank == 1
    assert results[0].rerank_score >= results[1].rerank_score


def test_final_top_k_is_respected() -> None:
    candidates = [_candidate(f"c{i}", f"word{i}") for i in range(10)]
    reranker = _reranker_with_fake_model()
    results = reranker.rerank("query", candidates, top_k=3)
    assert len(results) == 3


def test_candidate_pool_size_can_exceed_final_top_k() -> None:
    candidates = [_candidate(f"c{i}", "photosynthesis") for i in range(20)]
    reranker = _reranker_with_fake_model()
    results = reranker.rerank("photosynthesis", candidates, top_k=5)
    assert len(results) == 5


def test_metadata_and_fusion_info_preserved() -> None:
    candidates = [_candidate("c1", "photosynthesis energy", fused_score=0.777)]
    candidates[0].page = 4
    candidates[0].section = "Section 1.1"
    reranker = _reranker_with_fake_model()
    results = reranker.rerank("photosynthesis", candidates, top_k=1)
    assert results[0].fused_score == 0.777
    assert results[0].page == 4
    assert results[0].section == "Section 1.1"
    assert results[0].source_ranks == {"bm25": 1}


def test_tie_handling_deterministic() -> None:
    candidates = [
        _candidate("z", "same words here"),
        _candidate("a", "same words here"),
    ]
    reranker = _reranker_with_fake_model()
    results = reranker.rerank("same words here", candidates, top_k=2)
    assert results[0].rerank_score == results[1].rerank_score
    assert [r.chunk_id for r in results] == ["a", "z"]


def test_empty_candidates_returns_empty() -> None:
    reranker = _reranker_with_fake_model()
    assert reranker.rerank("query", [], top_k=5) == []

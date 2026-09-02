from __future__ import annotations

from app.retrieval.models import RetrievalCandidate
from app.retrieval.rrf import RRFFusion


def _candidate(chunk_id: str, rank: int, score: float = 0.0) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id, document_id="doc-1", content=f"content-{chunk_id}", rank=rank, score=score
    )


def test_rrf_hand_computed_scores_k_60() -> None:
    """Ranking A: A, B, C. Ranking B: B, D, A. k=60 (default/EduRAG value).

    RRF_score(d) = sum over lists containing d of 1 / (k + rank_i(d))

    A: rank 1 in list A, rank 3 in list B -> 1/61 + 1/63
    B: rank 2 in list A, rank 1 in list B -> 1/62 + 1/61
    C: rank 3 in list A only               -> 1/63
    D: rank 2 in list B only               -> 1/62
    """
    list_a = [_candidate("A", 1), _candidate("B", 2), _candidate("C", 3)]
    list_b = [_candidate("B", 1), _candidate("D", 2), _candidate("A", 3)]

    fused = RRFFusion(k=60).fuse({"a": list_a, "b": list_b})
    scores = {f.chunk_id: f.fused_score for f in fused}

    expected_a = 1 / 61 + 1 / 63
    expected_b = 1 / 62 + 1 / 61
    expected_c = 1 / 63
    expected_d = 1 / 62

    assert scores["A"] == expected_a
    assert scores["B"] == expected_b
    assert scores["C"] == expected_c
    assert scores["D"] == expected_d

    # B (0.03252) > A (0.03227) > D (0.01613) > C (0.01587)
    assert [f.chunk_id for f in fused] == ["B", "A", "D", "C"]
    assert [f.rank for f in fused] == [1, 2, 3, 4]


def test_rrf_preserves_source_ranks_and_scores() -> None:
    list_a = [_candidate("A", 1, score=5.0)]
    list_b = [_candidate("A", 2, score=0.9)]
    fused = RRFFusion(k=60).fuse({"bm25": list_a, "dense": list_b})
    assert fused[0].source_ranks == {"bm25": 1, "dense": 2}
    assert fused[0].source_scores == {"bm25": 5.0, "dense": 0.9}


def test_rrf_dedupes_chunk_appearing_in_both_lists() -> None:
    list_a = [_candidate("A", 1), _candidate("B", 2)]
    list_b = [_candidate("A", 1), _candidate("C", 2)]
    fused = RRFFusion(k=60).fuse({"a": list_a, "b": list_b})
    assert len({f.chunk_id for f in fused}) == 3
    assert len(fused) == 3


def test_rrf_configurable_k_changes_scores() -> None:
    list_a = [_candidate("A", 1)]
    fused_k1 = RRFFusion(k=1).fuse({"a": list_a})
    fused_k60 = RRFFusion(k=60).fuse({"a": list_a})
    assert fused_k1[0].fused_score == 1 / 2
    assert fused_k60[0].fused_score == 1 / 61
    assert fused_k1[0].fused_score != fused_k60[0].fused_score


def test_rrf_deterministic_tie_breaking() -> None:
    # Both chunks rank 1st in one list and 2nd in the other -> tied scores.
    list_a = [_candidate("z", 1), _candidate("a", 2)]
    list_b = [_candidate("a", 1), _candidate("z", 2)]
    fused = RRFFusion(k=60).fuse({"a": list_a, "b": list_b})
    assert fused[0].fused_score == fused[1].fused_score
    # tie broken by chunk_id ascending
    assert [f.chunk_id for f in fused] == ["a", "z"]


def test_rrf_empty_lists_returns_empty() -> None:
    assert RRFFusion(k=60).fuse({"a": [], "b": []}) == []


def test_rrf_single_list_ordering_unchanged() -> None:
    list_a = [_candidate("A", 1), _candidate("B", 2), _candidate("C", 3)]
    fused = RRFFusion(k=60).fuse({"a": list_a})
    assert [f.chunk_id for f in fused] == ["A", "B", "C"]

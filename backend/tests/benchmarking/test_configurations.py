from app.benchmarking.configurations import simple_score_fusion
from app.retrieval.models import RetrievalCandidate


def candidate(chunk_id: str, rank: int, score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id, document_id="doc1", content="x", rank=rank, score=score
    )


def test_simple_score_fusion_prefers_chunk_strong_in_both_sources():
    bm25 = [candidate("a", 1, 10.0), candidate("b", 2, 1.0)]
    dense = [candidate("a", 1, 0.9), candidate("c", 2, 0.5)]
    result = simple_score_fusion(bm25, dense, top_k=3)
    assert result[0] == "a"  # normalized score 1.0 + 1.0 = 2.0, highest


def test_simple_score_fusion_includes_chunk_from_only_one_source():
    bm25 = [candidate("a", 1, 10.0)]
    dense = [candidate("b", 1, 0.9)]
    result = simple_score_fusion(bm25, dense, top_k=5)
    assert set(result) == {"a", "b"}


def test_simple_score_fusion_respects_top_k():
    bm25 = [candidate(f"c{i}", i, float(10 - i)) for i in range(5)]
    result = simple_score_fusion(bm25, [], top_k=2)
    assert len(result) == 2


def test_simple_score_fusion_empty_inputs_returns_empty():
    assert simple_score_fusion([], [], top_k=5) == []


def test_simple_score_fusion_deterministic_tiebreak_by_chunk_id():
    bm25 = [candidate("b", 1, 1.0), candidate("a", 1, 1.0)]
    result = simple_score_fusion(bm25, [], top_k=2)
    assert result == ["a", "b"]

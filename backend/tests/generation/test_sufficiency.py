from __future__ import annotations

from app.generation.sufficiency import HeuristicSufficiencyChecker, SufficiencyConfig
from app.retrieval.models import RetrievalSource
from tests.generation.conftest import make_result

CONFIG = SufficiencyConfig(min_chunks=1, min_lexical_overlap=0.1, min_reranker_score=0.0)


def test_sufficient_when_lexical_overlap_is_high() -> None:
    checker = HeuristicSufficiencyChecker(CONFIG)
    evidence = [make_result("c1", "Photosynthesis converts light energy into chemical energy.")]
    result = checker.check("What is photosynthesis?", evidence)
    assert result.sufficient is True
    assert result.signals["chunk_count"] == 1


def test_sufficient_when_reranker_score_is_high_even_with_low_overlap() -> None:
    checker = HeuristicSufficiencyChecker(CONFIG)
    evidence = [
        make_result(
            "c1",
            "Zzz unrelated filler wording that shares nothing with the question.",
            rerank_score=5.0,
            retrieval_source=RetrievalSource.RERANKER,
        )
    ]
    result = checker.check("What is photosynthesis?", evidence)
    assert result.sufficient is True


def test_insufficient_when_no_evidence_retrieved() -> None:
    checker = HeuristicSufficiencyChecker(CONFIG)
    result = checker.check("What is photosynthesis?", [])
    assert result.sufficient is False
    assert result.signals["chunk_count"] == 0


def test_insufficient_when_below_min_chunks() -> None:
    checker = HeuristicSufficiencyChecker(SufficiencyConfig(2, 0.0, 0.0))
    evidence = [make_result("c1", "Photosynthesis converts light energy into chemical energy.")]
    result = checker.check("What is photosynthesis?", evidence)
    assert result.sufficient is False


def test_insufficient_when_low_score_and_low_overlap() -> None:
    checker = HeuristicSufficiencyChecker(SufficiencyConfig(1, 0.5, 10.0))
    evidence = [
        make_result(
            "c1",
            "Completely unrelated content about something else entirely.",
            rerank_score=-3.0,
        )
    ]
    result = checker.check("What is photosynthesis?", evidence)
    assert result.sufficient is False
    assert "does not appear to address" in result.reason


def test_result_is_deterministic() -> None:
    checker = HeuristicSufficiencyChecker(CONFIG)
    evidence = [make_result("c1", "Photosynthesis converts light energy into chemical energy.")]
    result_a = checker.check("What is photosynthesis?", evidence)
    result_b = checker.check("What is photosynthesis?", evidence)
    assert result_a.sufficient == result_b.sufficient
    assert result_a.signals == result_b.signals

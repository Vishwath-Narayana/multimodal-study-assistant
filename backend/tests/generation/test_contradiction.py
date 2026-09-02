from __future__ import annotations

from app.generation.contradiction import ContradictionConfig, LexicalContradictionChecker
from tests.generation.conftest import make_result


def test_consistent_sources_report_no_conflict() -> None:
    checker = LexicalContradictionChecker(ContradictionConfig(topic_overlap_threshold=0.2))
    evidence = [
        make_result("c1", "Photosynthesis converts light energy into chemical energy."),
        make_result("c2", "Cellular respiration releases energy stored in glucose."),
    ]
    result = checker.check(evidence)
    assert result.has_conflict is False
    assert result.conflicts == []


def test_conflicting_sources_flagged_via_antonym_pair() -> None:
    checker = LexicalContradictionChecker(ContradictionConfig(topic_overlap_threshold=0.1))
    evidence = [
        make_result("c1", "Caching latency increases when the cache is cold."),
        make_result("c2", "Caching latency decreases when the cache is cold."),
    ]
    result = checker.check(evidence)
    assert result.has_conflict is True
    assert result.conflicts[0].chunk_id_a == "c1"
    assert result.conflicts[0].chunk_id_b == "c2"


def test_conflicting_sources_flagged_via_negation_mismatch() -> None:
    checker = LexicalContradictionChecker(ContradictionConfig(topic_overlap_threshold=0.1))
    evidence = [
        make_result("c1", "The algorithm terminates for all valid inputs."),
        make_result("c2", "The algorithm does not terminate for all valid inputs."),
    ]
    result = checker.check(evidence)
    assert result.has_conflict is True


def test_no_evidence_returns_no_conflict() -> None:
    checker = LexicalContradictionChecker()
    result = checker.check([])
    assert result.has_conflict is False


def test_single_chunk_cannot_conflict() -> None:
    checker = LexicalContradictionChecker()
    evidence = [make_result("c1", "Photosynthesis converts light energy.")]
    result = checker.check(evidence)
    assert result.has_conflict is False


def test_result_is_deterministic() -> None:
    checker = LexicalContradictionChecker(ContradictionConfig(topic_overlap_threshold=0.1))
    evidence = [
        make_result("c1", "Caching latency increases when the cache is cold."),
        make_result("c2", "Caching latency decreases when the cache is cold."),
    ]
    first = checker.check(evidence)
    second = checker.check(evidence)
    assert first.has_conflict == second.has_conflict
    assert len(first.conflicts) == len(second.conflicts)

"""Hand-computed examples for the Phase 4 multimodal evaluation metrics."""

from __future__ import annotations

import pytest

from app.multimodal.evaluation.metrics import (
    table_retrieval_accuracy,
    timestamp_citation_accuracy,
    transcript_retrieval_accuracy,
    visual_metrics,
)


def test_visual_metrics_only_scores_image_tagged_queries() -> None:
    retrieved = [["c1", "c2"], ["c3", "c4"], ["c5", "c6"]]
    relevant = [{"c1"}, {"c3"}, {"c9"}]
    modality = ["image", "table", "image"]

    result = visual_metrics(retrieved, relevant, modality)

    # Only queries 0 and 2 are "image": query 0 hits at rank 1 (RR=1.0),
    # query 2 misses entirely (RR=0.0) -> mean MRR = 0.5.
    assert result.query_count == 2
    assert result.mrr == pytest.approx(0.5)


def test_table_retrieval_accuracy_scopes_to_table_queries() -> None:
    retrieved = [["c1"], ["c2"], ["c3"]]
    relevant = [{"c1"}, {"c2"}, {"c1"}]
    modality = ["table", "table", "image"]

    result = table_retrieval_accuracy(retrieved, relevant, modality)
    assert result.query_count == 2
    assert result.mrr == pytest.approx(1.0)  # both table queries hit at rank 1


def test_transcript_retrieval_accuracy_scopes_to_transcript_queries() -> None:
    retrieved = [["c1"], ["c2"]]
    relevant = [{"c9"}, {"c2"}]
    modality = ["transcript", "transcript"]

    result = transcript_retrieval_accuracy(retrieved, relevant, modality)
    assert result.query_count == 2
    assert result.recall_at_1 == pytest.approx(0.5)


def test_modality_metrics_empty_subset_returns_zero_query_count() -> None:
    result = visual_metrics([["c1"]], [{"c1"}], ["table"])
    assert result.query_count == 0
    assert result.mrr == 0.0


def test_modality_metrics_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError):
        visual_metrics([["c1"]], [{"c1"}, {"c2"}], ["image"])


def test_timestamp_citation_accuracy_exact_match() -> None:
    predicted = [(751.0, 788.0)]
    gold = [(751.0, 788.0)]
    assert timestamp_citation_accuracy(predicted, gold) == 1.0


def test_timestamp_citation_accuracy_within_tolerance() -> None:
    predicted = [(752.5, 789.0)]
    gold = [(751.0, 788.0)]
    assert timestamp_citation_accuracy(predicted, gold, tolerance_seconds=2.0) == 1.0


def test_timestamp_citation_accuracy_outside_tolerance() -> None:
    predicted = [(760.0, 795.0)]
    gold = [(751.0, 788.0)]
    assert timestamp_citation_accuracy(predicted, gold, tolerance_seconds=2.0) == 0.0


def test_timestamp_citation_accuracy_mixed_hits() -> None:
    predicted = [(751.0, 788.0), (900.0, 920.0)]
    gold = [(751.0, 788.0), (500.0, 520.0)]
    assert timestamp_citation_accuracy(predicted, gold) == 0.5


def test_timestamp_citation_accuracy_empty_gold_returns_zero() -> None:
    assert timestamp_citation_accuracy([], []) == 0.0


def test_timestamp_citation_accuracy_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError):
        timestamp_citation_accuracy([(1.0, 2.0)], [(1.0, 2.0), (3.0, 4.0)])

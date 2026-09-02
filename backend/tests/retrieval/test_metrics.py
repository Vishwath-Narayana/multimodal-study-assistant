from __future__ import annotations

import pytest

from app.retrieval.evaluation.metrics import (
    aggregate,
    hit_rate_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_reciprocal_rank_first_position() -> None:
    assert reciprocal_rank(["a", "b", "c"], {"a"}) == 1.0


def test_reciprocal_rank_third_position() -> None:
    assert reciprocal_rank(["x", "y", "a"], {"a"}) == 1 / 3


def test_reciprocal_rank_not_found() -> None:
    assert reciprocal_rank(["x", "y", "z"], {"a"}) == 0.0


def test_recall_at_k_hand_computed() -> None:
    # 2 relevant chunks total, only 1 appears in the top 3 retrieved.
    retrieved = ["x", "a", "y"]
    relevant = {"a", "b"}
    assert recall_at_k(retrieved, relevant, k=3) == 0.5


def test_recall_at_1_hand_computed() -> None:
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b"}
    assert recall_at_k(retrieved, relevant, k=1) == 0.5


def test_recall_at_k_empty_relevant_returns_zero() -> None:
    assert recall_at_k(["a", "b"], set(), k=5) == 0.0


def test_precision_at_k_hand_computed() -> None:
    # top-3 retrieved: a (relevant), x (not), b (relevant) -> 2/3.
    retrieved = ["a", "x", "b"]
    relevant = {"a", "b", "c"}
    assert precision_at_k(retrieved, relevant, k=3) == 2 / 3


def test_precision_at_k_short_list_penalized() -> None:
    # Only 1 item retrieved, k=5 -> denominator stays 5.
    retrieved = ["a"]
    relevant = {"a"}
    assert precision_at_k(retrieved, relevant, k=5) == 1 / 5


def test_hit_rate_at_k_hit() -> None:
    assert hit_rate_at_k(["x", "a"], {"a"}, k=2) == 1.0


def test_hit_rate_at_k_miss() -> None:
    assert hit_rate_at_k(["x", "y"], {"a"}, k=2) == 0.0


def test_aggregate_mrr_across_three_queries() -> None:
    # Query 1: relevant found at rank 1 -> RR=1.0
    # Query 2: relevant found at rank 2 -> RR=0.5
    # Query 3: relevant not found      -> RR=0.0
    # MRR = (1.0 + 0.5 + 0.0) / 3 = 0.5
    retrieved = [["a", "x"], ["x", "a"], ["x", "y"]]
    relevant = [{"a"}, {"a"}, {"a"}]
    result = aggregate(retrieved, relevant)
    assert result.mrr == 0.5
    assert result.query_count == 3


def test_aggregate_empty_dataset_returns_zeros() -> None:
    result = aggregate([], [])
    assert result.mrr == 0.0
    assert result.query_count == 0


def test_aggregate_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        aggregate([["a"]], [{"a"}, {"b"}])

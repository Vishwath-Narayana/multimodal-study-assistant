from app.benchmarking.metrics_ext import (
    aggregate_metrics,
    breakdown_by,
    compute_query_metrics,
    dcg_at_k,
    ndcg_at_k,
)


def test_ndcg_at_k_perfect_ranking_is_one():
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b"}
    assert ndcg_at_k(retrieved, relevant, 5) == 1.0


def test_ndcg_at_k_worse_ranking_scores_lower_than_perfect():
    relevant = {"a", "b"}
    perfect = ndcg_at_k(["a", "b", "c"], relevant, 5)
    worse = ndcg_at_k(["c", "d", "a"], relevant, 5)
    assert worse < perfect


def test_ndcg_at_k_no_relevant_is_zero():
    assert ndcg_at_k([], set(), 5) == 0.0


def test_dcg_at_k_ignores_items_past_k():
    retrieved = ["irrelevant"] * 10 + ["a"]
    assert dcg_at_k(retrieved, {"a"}, 5) == 0.0


def test_compute_query_metrics_hand_checked_example():
    # relevant chunk found at rank 2 out of 3 retrieved.
    m = compute_query_metrics(
        query_id="q1",
        category="factual",
        modality="text",
        retrieved=["x", "a", "y"],
        relevant={"a"},
        latency_ms=12.5,
    )
    assert m.reciprocal_rank == 0.5
    assert m.recall_at_1 == 0.0
    assert m.recall_at_3 == 1.0
    assert m.precision_at_1 == 0.0
    assert m.hit_rate_at_5 == 1.0
    assert m.latency_ms == 12.5
    assert m.error is None


def test_aggregate_metrics_is_the_mean_across_queries():
    m1 = compute_query_metrics("q1", "factual", "text", ["a"], {"a"}, 10.0)
    m2 = compute_query_metrics("q2", "factual", "text", ["b"], {"a"}, 20.0)
    agg = aggregate_metrics([m1, m2])
    assert agg["reciprocal_rank"] == 0.5  # (1.0 + 0.0) / 2
    assert agg["latency_ms"] == 15.0


def test_aggregate_metrics_empty_list_is_all_zero():
    agg = aggregate_metrics([])
    assert all(v == 0.0 for v in agg.values())


def test_breakdown_by_category_groups_correctly():
    m1 = compute_query_metrics("q1", "factual", "text", ["a"], {"a"}, 10.0)
    m2 = compute_query_metrics("q2", "definition", "text", ["b"], {"a"}, 10.0)
    breakdown = breakdown_by([m1, m2], "category")
    assert set(breakdown) == {"factual", "definition"}
    assert breakdown["factual"]["reciprocal_rank"] == 1.0
    assert breakdown["definition"]["reciprocal_rank"] == 0.0

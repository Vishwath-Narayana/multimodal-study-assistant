"""Retrieval evaluation metrics, implemented directly (not delegated to an
external eval framework) so the math is auditable and unit-testable with
hand-computed examples.

All functions take a ranked list of retrieved chunk ids (best-first) and a
set of relevant chunk ids for one query, and are pure/stateless — no
hidden state, no coupling to `RetrievalResult` (kept generic so the
experiment runner and any future caller can use them identically).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


def reciprocal_rank(retrieved: Sequence[str], relevant: set[str]) -> float:
    """1 / (rank of the first relevant item), 0.0 if none of `retrieved` is
    relevant. Rank is 1-indexed."""
    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in relevant:
            return 1.0 / rank
    return 0.0


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Fraction of `relevant` chunks present in the top-k of `retrieved`.

    0.0 if `relevant` is empty (nothing to recall) rather than raising or
    returning NaN, so aggregation never has to special-case it.
    """
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    return len(top_k & relevant) / len(relevant)


def precision_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Fraction of the top-k `retrieved` items that are relevant.

    0.0 if fewer than `k` items were retrieved at all (the denominator is
    still `k`, per the standard precision@k definition — a short result
    list is penalized, not silently rescaled).
    """
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for chunk_id in top_k if chunk_id in relevant)
    return hits / k


def hit_rate_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """1.0 if at least one relevant chunk appears in the top-k, else 0.0."""
    return 1.0 if set(retrieved[:k]) & relevant else 0.0


@dataclass
class AggregateMetrics:
    mrr: float
    recall_at_1: float
    recall_at_5: float
    precision_at_5: float
    hit_rate_at_5: float
    query_count: int


def aggregate(
    per_query_retrieved: Sequence[Sequence[str]],
    per_query_relevant: Sequence[set[str]],
) -> AggregateMetrics:
    """Mean of each metric across queries. Both sequences must be the same
    length and index-aligned (query i's retrieved list <-> relevant set)."""
    if len(per_query_retrieved) != len(per_query_relevant):
        raise ValueError("per_query_retrieved and per_query_relevant must be the same length.")
    n = len(per_query_retrieved)
    if n == 0:
        return AggregateMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0)

    pairs = list(zip(per_query_retrieved, per_query_relevant, strict=True))
    rr = [reciprocal_rank(r, rel) for r, rel in pairs]
    r1 = [recall_at_k(r, rel, 1) for r, rel in pairs]
    r5 = [recall_at_k(r, rel, 5) for r, rel in pairs]
    p5 = [precision_at_k(r, rel, 5) for r, rel in pairs]
    h5 = [hit_rate_at_k(r, rel, 5) for r, rel in pairs]

    return AggregateMetrics(
        mrr=sum(rr) / n,
        recall_at_1=sum(r1) / n,
        recall_at_5=sum(r5) / n,
        precision_at_5=sum(p5) / n,
        hit_rate_at_5=sum(h5) / n,
        query_count=n,
    )

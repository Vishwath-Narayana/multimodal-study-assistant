"""Phase 7 metric additions on top of the existing, unchanged Phase 2
`app.retrieval.evaluation.metrics` (reciprocal_rank/recall_at_k/
precision_at_k/hit_rate_at_k/aggregate) — this module only adds nDCG and
by-category/by-modality breakdowns, it does not reimplement anything
already there.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field


def dcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Binary-relevance DCG@k: relevant chunk = gain 1, else 0."""
    total = 0.0
    for i, chunk_id in enumerate(retrieved[:k], start=1):
        if chunk_id in relevant:
            total += 1.0 / math.log2(i + 1)
    return total


def ndcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """nDCG@k normalized against the ideal ordering (all relevant chunks
    first, up to min(k, len(relevant)))."""
    if not relevant:
        return 0.0
    ideal_hits = min(k, len(relevant))
    ideal_dcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    if ideal_dcg == 0.0:
        return 0.0
    return dcg_at_k(retrieved, relevant, k) / ideal_dcg


@dataclass
class QueryMetrics:
    query_id: str
    category: str
    modality: str
    reciprocal_rank: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    precision_at_1: float
    precision_at_5: float
    precision_at_10: float
    hit_rate_at_5: float
    ndcg_at_5: float
    ndcg_at_10: float
    latency_ms: float
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    relevant_chunk_ids: list[str] = field(default_factory=list)
    error: str | None = None


def compute_query_metrics(
    query_id: str,
    category: str,
    modality: str,
    retrieved: list[str],
    relevant: set[str],
    latency_ms: float,
    error: str | None = None,
) -> QueryMetrics:
    from app.retrieval.evaluation.metrics import (
        hit_rate_at_k,
        precision_at_k,
        recall_at_k,
        reciprocal_rank,
    )

    return QueryMetrics(
        query_id=query_id,
        category=category,
        modality=modality,
        reciprocal_rank=reciprocal_rank(retrieved, relevant),
        recall_at_1=recall_at_k(retrieved, relevant, 1),
        recall_at_3=recall_at_k(retrieved, relevant, 3),
        recall_at_5=recall_at_k(retrieved, relevant, 5),
        recall_at_10=recall_at_k(retrieved, relevant, 10),
        precision_at_1=precision_at_k(retrieved, relevant, 1),
        precision_at_5=precision_at_k(retrieved, relevant, 5),
        precision_at_10=precision_at_k(retrieved, relevant, 10),
        hit_rate_at_5=hit_rate_at_k(retrieved, relevant, 5),
        ndcg_at_5=ndcg_at_k(retrieved, relevant, 5),
        ndcg_at_10=ndcg_at_k(retrieved, relevant, 10),
        latency_ms=latency_ms,
        retrieved_chunk_ids=list(retrieved),
        relevant_chunk_ids=sorted(relevant),
        error=error,
    )


_NUMERIC_FIELDS = (
    "reciprocal_rank",
    "recall_at_1",
    "recall_at_3",
    "recall_at_5",
    "recall_at_10",
    "precision_at_1",
    "precision_at_5",
    "precision_at_10",
    "hit_rate_at_5",
    "ndcg_at_5",
    "ndcg_at_10",
    "latency_ms",
)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate_metrics(results: list[QueryMetrics]) -> dict[str, float]:
    if not results:
        return dict.fromkeys(_NUMERIC_FIELDS, 0.0)
    return {
        field_name: _mean([getattr(r, field_name) for r in results])
        for field_name in _NUMERIC_FIELDS
    }


def breakdown_by(results: list[QueryMetrics], attr: str) -> dict[str, dict[str, float]]:
    """attr is 'category' or 'modality'."""
    groups: dict[str, list[QueryMetrics]] = {}
    for r in results:
        groups.setdefault(getattr(r, attr), []).append(r)
    return {key: aggregate_metrics(group) for key, group in groups.items()}

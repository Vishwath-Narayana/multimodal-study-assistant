"""Multimodal evaluation metrics (spec section 28).

Visual/table/transcript retrieval accuracy are **not new math** — they are
the same rank-based metrics `app.retrieval.evaluation.metrics` already
implements and unit-tests, applied to the subset of queries whose relevant
evidence is of a given modality. Reusing `aggregate()`/`reciprocal_rank()`/
`recall_at_k()` here (rather than reimplementing MRR/Recall a second time)
is deliberate: a "Visual MRR" that used different math from the existing
MRR would not be comparable to it.

`timestamp_citation_accuracy` is the one genuinely new metric: whether a
transcript citation's `audio_start`/`audio_end` actually falls within the
gold segment it claims to cite, which has no text-retrieval equivalent.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.retrieval.evaluation.metrics import AggregateMetrics, aggregate


def modality_subset_metrics(
    per_query_retrieved: Sequence[Sequence[str]],
    per_query_relevant: Sequence[set[str]],
    per_query_modality: Sequence[str],
    modality: str,
) -> AggregateMetrics:
    """`aggregate()` restricted to queries tagged with `modality` (e.g.
    "image", "table", "transcript") — this is what "Visual MRR"/"Table
    retrieval accuracy"/"Transcript retrieval accuracy" mean in
    docs/research/evaluation-plan.md: the same MRR/Recall@5 computation,
    scoped to one modality's queries rather than the whole dataset.

    All three sequences must be the same length and index-aligned (query i's
    retrieved list / relevant set / modality tag).
    """
    if not (len(per_query_retrieved) == len(per_query_relevant) == len(per_query_modality)):
        raise ValueError("All three per-query sequences must be the same length.")

    indices = [i for i, m in enumerate(per_query_modality) if m == modality]
    filtered_retrieved = [per_query_retrieved[i] for i in indices]
    filtered_relevant = [per_query_relevant[i] for i in indices]
    return aggregate(filtered_retrieved, filtered_relevant)


def visual_metrics(
    per_query_retrieved: Sequence[Sequence[str]],
    per_query_relevant: Sequence[set[str]],
    per_query_modality: Sequence[str],
) -> AggregateMetrics:
    """Visual MRR / Visual Recall@5, scoped to `modality == "image"` queries."""
    return modality_subset_metrics(
        per_query_retrieved, per_query_relevant, per_query_modality, "image"
    )


def table_retrieval_accuracy(
    per_query_retrieved: Sequence[Sequence[str]],
    per_query_relevant: Sequence[set[str]],
    per_query_modality: Sequence[str],
) -> AggregateMetrics:
    return modality_subset_metrics(
        per_query_retrieved, per_query_relevant, per_query_modality, "table"
    )


def transcript_retrieval_accuracy(
    per_query_retrieved: Sequence[Sequence[str]],
    per_query_relevant: Sequence[set[str]],
    per_query_modality: Sequence[str],
) -> AggregateMetrics:
    return modality_subset_metrics(
        per_query_retrieved, per_query_relevant, per_query_modality, "transcript"
    )


def timestamp_citation_accuracy(
    predicted: Sequence[tuple[float, float]],
    gold: Sequence[tuple[float, float]],
    *,
    tolerance_seconds: float = 2.0,
) -> float:
    """Fraction of `predicted` (audio_start, audio_end) citations whose
    start falls within `tolerance_seconds` of the index-aligned gold
    segment's start (spec: "Timestamp citation accuracy"). `predicted` and
    `gold` must be the same length and index-aligned (prediction i answers
    gold segment i) — 0.0 for an empty input rather than raising or NaN,
    matching `app.retrieval.evaluation.metrics`'s convention.
    """
    if not gold:
        return 0.0
    if len(predicted) != len(gold):
        raise ValueError("predicted and gold must be the same length.")

    hits = sum(
        1
        for (pred_start, _pred_end), (gold_start, _gold_end) in zip(predicted, gold, strict=True)
        if abs(pred_start - gold_start) <= tolerance_seconds
    )
    return hits / len(gold)

"""Study Engine evaluation metrics (spec section 28).

Extends the existing Phase 3 evaluation framework rather than inventing a
parallel one: summarization text-quality metrics (`token_f1`, `rouge_l`)
are imported directly from `app.generation.evaluation.metrics` — no
re-implementation — since a generated summary's text-similarity-to-
reference scoring is identical math regardless of which pipeline produced
the text. `bertscore_f1` stays intentionally unavailable for the same
reason it is in Phase 3 (no optional `bert-score` dependency installed).

Everything below operates on `app.study.models` types already produced by
`StudyEngineService`, the same "compute from what the service already
returns" approach `app.generation.evaluation.metrics.compute_trust_metrics`
uses — no ground-truth study-item text is required for these structural/
trust metrics (only `StudyExample`'s optional `gold_answerable` needs a
human/gold label, for the abstention-correctness metrics).

No benchmark numbers are reported anywhere in this module or its tests —
computing these against a real model run is future work (spec section 28:
"Actual measurement requires a real dataset/model run").
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.generation.evaluation.metrics import rouge_l as rouge_l
from app.generation.evaluation.metrics import token_f1 as token_f1
from app.study.models import StudyGenerationStats


@dataclass
class StudyTrustExample:
    """One evaluated study-generation request's inputs to
    `compute_study_trust_metrics`.

    `gold_answerable`, when known (e.g. from a curated eval set), enables
    the abstention-correctness metrics; otherwise leave it `None` and those
    metrics come back `None` rather than a misleading guess — same
    discipline as `app.generation.evaluation.metrics.TrustExample`.
    """

    answerable: bool
    stats: StudyGenerationStats
    citation_valid_flags: list[bool]
    gold_answerable: bool | None = None


@dataclass
class StudyTrustMetrics:
    """Aggregate structural/trust metrics over a batch of study-generation
    results — spec section 28's "Quiz"/"MCQ"/"Flashcards"/"Overall" metric
    groups collapse into one shape here since they are computed the same
    way regardless of mode (structural validity, source support, duplicate
    rate, citation validity, abstention correctness); a per-mode breakdown
    is obtained by calling this once per mode's example batch.

    `None` fields mean "not computable from the given inputs", never a
    silently substituted 0.0/1.0.
    """

    grounded_item_rate: float | None
    """validated_count / generated_count, averaged over requests that
    generated at least one item — spec's "grounded-study-item rate"."""

    duplicate_rate: float | None
    """duplicate_count / (validated_count + duplicate_count), i.e. the
    share of accepted-shape items that were dropped as near-duplicates."""

    citation_validity_rate: float | None
    correct_abstention_rate: float | None
    false_answer_rate: float | None
    example_count: int


def compute_study_trust_metrics(
    examples: Sequence[StudyTrustExample],
) -> StudyTrustMetrics:
    n = len(examples)
    if n == 0:
        return StudyTrustMetrics(None, None, None, None, None, 0)

    grounded_ratios = [
        ex.stats.validated_count / ex.stats.generated_count
        for ex in examples
        if ex.stats.generated_count > 0
    ]
    grounded_item_rate = sum(grounded_ratios) / len(grounded_ratios) if grounded_ratios else None

    dup_ratios = []
    for ex in examples:
        denom = ex.stats.validated_count + ex.stats.duplicate_count
        if denom > 0:
            dup_ratios.append(ex.stats.duplicate_count / denom)
    duplicate_rate = sum(dup_ratios) / len(dup_ratios) if dup_ratios else None

    all_flags = [flag for ex in examples for flag in ex.citation_valid_flags]
    citation_validity_rate = sum(all_flags) / len(all_flags) if all_flags else None

    labeled = [ex for ex in examples if ex.gold_answerable is not None]
    if labeled:
        should_abstain = [ex for ex in labeled if ex.gold_answerable is False]
        correct_abstentions = [ex for ex in should_abstain if ex.answerable is False]
        false_answers = [ex for ex in should_abstain if ex.answerable is True]
        correct_abstention_rate = (
            len(correct_abstentions) / len(should_abstain) if should_abstain else None
        )
        false_answer_rate = len(false_answers) / len(should_abstain) if should_abstain else None
    else:
        correct_abstention_rate = None
        false_answer_rate = None

    return StudyTrustMetrics(
        grounded_item_rate=grounded_item_rate,
        duplicate_rate=duplicate_rate,
        citation_validity_rate=citation_validity_rate,
        correct_abstention_rate=correct_abstention_rate,
        false_answer_rate=false_answer_rate,
        example_count=n,
    )

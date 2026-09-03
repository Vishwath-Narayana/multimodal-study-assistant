from __future__ import annotations

from app.study.evaluation.dataset import load_study_eval_dataset
from app.study.evaluation.metrics import (
    StudyTrustExample,
    compute_study_trust_metrics,
    rouge_l,
    token_f1,
)
from app.study.models import StudyGenerationStats


def test_load_study_eval_dataset_covers_every_mode() -> None:
    dataset = load_study_eval_dataset()
    modes = {ex.mode for ex in dataset.examples}
    assert modes == {"summary", "explain", "compare", "quiz", "mcq", "flashcards"}


def test_reused_text_metrics_are_importable_and_functional() -> None:
    assert token_f1("a b c", "a b c") == 1.0
    assert rouge_l("a b c", "a b c") == 1.0


def test_compute_study_trust_metrics_empty() -> None:
    metrics = compute_study_trust_metrics([])
    assert metrics.example_count == 0
    assert metrics.grounded_item_rate is None


def test_compute_study_trust_metrics_grounded_item_rate() -> None:
    examples = [
        StudyTrustExample(
            answerable=True,
            stats=StudyGenerationStats(
                requested_count=5, generated_count=5, validated_count=4, rejected_count=1
            ),
            citation_valid_flags=[True, True, False],
        )
    ]
    metrics = compute_study_trust_metrics(examples)
    assert metrics.grounded_item_rate == 0.8
    assert metrics.citation_validity_rate == 2 / 3


def test_compute_study_trust_metrics_abstention_correctness() -> None:
    examples = [
        StudyTrustExample(
            answerable=False,
            stats=StudyGenerationStats(generated_count=0, validated_count=0),
            citation_valid_flags=[],
            gold_answerable=False,
        ),
        StudyTrustExample(
            answerable=True,
            stats=StudyGenerationStats(generated_count=2, validated_count=2),
            citation_valid_flags=[True],
            gold_answerable=False,
        ),
    ]
    metrics = compute_study_trust_metrics(examples)
    assert metrics.correct_abstention_rate == 0.5
    assert metrics.false_answer_rate == 0.5


def test_compute_study_trust_metrics_duplicate_rate() -> None:
    examples = [
        StudyTrustExample(
            answerable=True,
            stats=StudyGenerationStats(generated_count=3, validated_count=2, duplicate_count=1),
            citation_valid_flags=[True],
        )
    ]
    metrics = compute_study_trust_metrics(examples)
    assert metrics.duplicate_rate == 1 / 3

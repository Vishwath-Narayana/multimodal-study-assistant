from __future__ import annotations

import pytest

from app.generation.evaluation.metrics import (
    TrustExample,
    bertscore_f1,
    compute_trust_metrics,
    rouge_l,
    token_f1,
)
from app.generation.models import ClaimGrounding


def test_token_f1_identical_strings_is_one() -> None:
    text = "Photosynthesis converts light energy."
    assert token_f1(text, text) == 1.0


def test_token_f1_disjoint_strings_is_zero() -> None:
    assert token_f1("apple banana", "car truck") == 0.0


def test_token_f1_partial_overlap() -> None:
    score = token_f1("light energy conversion", "light energy transformation process")
    assert 0.0 < score < 1.0


def test_token_f1_both_empty_is_one() -> None:
    assert token_f1("", "") == 1.0


def test_token_f1_one_empty_is_zero() -> None:
    assert token_f1("something", "") == 0.0


def test_rouge_l_identical_strings_is_one() -> None:
    text = "Photosynthesis converts light energy."
    assert rouge_l(text, text) == 1.0


def test_rouge_l_no_common_subsequence_is_zero() -> None:
    assert rouge_l("apple banana", "car truck") == 0.0


def test_rouge_l_partial_overlap_between_zero_and_one() -> None:
    score = rouge_l("the cat sat on the mat", "the cat sat on a rug")
    assert 0.0 < score < 1.0


def test_bertscore_f1_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        bertscore_f1("a", "b")


def test_trust_metrics_empty_examples() -> None:
    metrics = compute_trust_metrics([])
    assert metrics.example_count == 0
    assert metrics.citation_validity_rate is None


def test_trust_metrics_citation_validity_rate() -> None:
    examples = [
        TrustExample(
            answerable=True, citation_valid_flags=[True, False], claim_groundings=[]
        ),
        TrustExample(answerable=True, citation_valid_flags=[True], claim_groundings=[]),
    ]
    metrics = compute_trust_metrics(examples)
    assert metrics.citation_validity_rate == pytest.approx(2 / 3)


def test_trust_metrics_unsupported_claim_rate() -> None:
    examples = [
        TrustExample(
            answerable=True,
            citation_valid_flags=[],
            claim_groundings=[
                ClaimGrounding(claim="a", supporting_chunk_ids=["c1"], grounding_ratio=0.9),
                ClaimGrounding(claim="b", supporting_chunk_ids=[], grounding_ratio=None),
            ],
        )
    ]
    metrics = compute_trust_metrics(examples)
    assert metrics.unsupported_claim_rate == 0.5


def test_trust_metrics_abstention_rates_need_gold_labels() -> None:
    examples = [TrustExample(answerable=False, citation_valid_flags=[], claim_groundings=[])]
    metrics = compute_trust_metrics(examples)
    assert metrics.correct_abstention_rate is None
    assert metrics.false_answer_rate is None


def test_trust_metrics_correct_and_false_abstention_with_gold_labels() -> None:
    examples = [
        TrustExample(
            answerable=False, citation_valid_flags=[], claim_groundings=[], gold_answerable=False
        ),
        TrustExample(
            answerable=True, citation_valid_flags=[], claim_groundings=[], gold_answerable=False
        ),
    ]
    metrics = compute_trust_metrics(examples)
    assert metrics.correct_abstention_rate == 0.5
    assert metrics.false_answer_rate == 0.5

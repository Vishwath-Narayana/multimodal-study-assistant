"""Generation/grounding evaluation metrics (spec section 20).

Implemented directly, the same discipline as
`app.retrieval.evaluation.metrics`: pure/stateless functions, auditable
with hand-computed examples, no coupling to a specific response schema.

**Generation quality** (`token_f1`, `rouge_l`): computable today with no
extra dependency, both operating on `app.retrieval.tokenizer.tokenize`
output for consistency with the rest of this codebase's token handling.
`bertscore_f1` is deliberately **not implemented** — it requires the
optional `bert-score` package (a real dependency: `transformers` + a
pretrained scoring model), which is not installed in this environment
(spec: "do not add unnecessary dependencies" / "do not fabricate real
model benchmark results"). Calling it raises `NotImplementedError` with a
pointer to how to enable it, rather than silently returning a fake number
or a stand-in metric mislabeled as BERTScore.

**Trust/grounding metrics** (`compute_trust_metrics`): computed directly
from `app.generation.models` types already produced by
`GenerationService.answer(...)` — no ground-truth answer text is needed
for these, only whether the system attempted an answer and how well cited/
grounded it was, plus (optionally) a human/gold "was this actually
answerable" label for the abstention-correctness metrics.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.generation.models import ClaimGrounding
from app.retrieval.tokenizer import tokenize


def token_f1(prediction: str, reference: str) -> float:
    """Unigram F1 over tokenized text — the standard QA "Token F1" metric
    (bag-of-tokens overlap, order-independent, no partial-credit stemming).
    1.0 for two empty strings (nothing to compare, trivially equal); 0.0 if
    exactly one of the two is empty.
    """
    pred_tokens = tokenize(prediction)
    ref_tokens = tokenize(reference)
    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0

    common: dict[str, int] = {}
    ref_counts: dict[str, int] = {}
    for token in ref_tokens:
        ref_counts[token] = ref_counts.get(token, 0) + 1
    pred_counts: dict[str, int] = {}
    for token in pred_tokens:
        pred_counts[token] = pred_counts.get(token, 0) + 1
    for token, count in pred_counts.items():
        common[token] = min(count, ref_counts.get(token, 0))

    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def _lcs_length(a: Sequence[str], b: Sequence[str]) -> int:
    if not a or not b:
        return 0
    previous = [0] * (len(b) + 1)
    for token_a in a:
        current = [0] * (len(b) + 1)
        for j, token_b in enumerate(b, start=1):
            if token_a == token_b:
                current[j] = previous[j - 1] + 1
            else:
                current[j] = max(previous[j], current[j - 1])
        previous = current
    return previous[-1]


def rouge_l(prediction: str, reference: str) -> float:
    """ROUGE-L F-measure: longest-common-subsequence-based precision/recall
    over tokenized text. A from-scratch LCS implementation (no `rouge-score`
    dependency) — matches the standard ROUGE-L *definition*, but has not
    been cross-validated numerically against the reference `rouge-score`
    package's output; treat small differences as possible on edge cases
    (e.g. its stemming/tokenization choices differ from ours).
    """
    pred_tokens = tokenize(prediction)
    ref_tokens = tokenize(reference)
    if not pred_tokens or not ref_tokens:
        return 0.0
    lcs = _lcs_length(pred_tokens, ref_tokens)
    if lcs == 0:
        return 0.0
    precision = lcs / len(pred_tokens)
    recall = lcs / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def bertscore_f1(prediction: str, reference: str) -> float:
    """Not implemented in this environment.

    BERTScore requires the optional `bert-score` package (which pulls in a
    pretrained transformer model for contextual embeddings) — not part of
    this project's dependency set. Enable it by adding `bert-score` to
    `backend/pyproject.toml` and implementing this function against its
    `bert_score.score(...)` API; until then, this raises rather than
    returning a fabricated or substitute number under the BERTScore name.
    """
    raise NotImplementedError(
        "BERTScore requires the optional 'bert-score' dependency, which is not "
        "installed. See docs/architecture/generation.md 'Evaluation' for details."
    )


@dataclass
class TrustMetrics:
    """Aggregate trust/grounding metrics over a batch of generation results.

    None fields mean "not computable from the given inputs" (e.g. abstention
    correctness needs a gold answerability label per example) rather than a
    silently substituted 0.0/1.0.
    """

    citation_validity_rate: float | None
    unsupported_claim_rate: float | None
    grounded_question_rate: float | None
    grounded_answer_rate: float | None
    correct_abstention_rate: float | None
    false_answer_rate: float | None
    example_count: int


@dataclass
class TrustExample:
    """One evaluated example's inputs to `compute_trust_metrics`.

    `gold_answerable`, when known (e.g. from a curated eval set), enables
    the abstention-correctness metrics; otherwise leave it `None` and those
    metrics come back `None` rather than a misleading guess.
    """

    answerable: bool
    citation_valid_flags: list[bool]
    claim_groundings: list[ClaimGrounding]
    unsupported_claim_threshold: float = 0.5
    gold_answerable: bool | None = None


def compute_trust_metrics(examples: Sequence[TrustExample]) -> TrustMetrics:
    n = len(examples)
    if n == 0:
        return TrustMetrics(None, None, None, None, None, None, 0)

    all_citation_flags = [flag for ex in examples for flag in ex.citation_valid_flags]
    citation_validity_rate = (
        sum(all_citation_flags) / len(all_citation_flags) if all_citation_flags else None
    )

    def _is_unsupported(claim: ClaimGrounding, threshold: float) -> bool:
        if not claim.supporting_chunk_ids:
            return True
        return claim.grounding_ratio is not None and claim.grounding_ratio < threshold

    all_claims = [claim for ex in examples for claim in ex.claim_groundings]
    unsupported = [
        claim
        for ex in examples
        for claim in ex.claim_groundings
        if _is_unsupported(claim, ex.unsupported_claim_threshold)
    ]
    unsupported_claim_rate = len(unsupported) / len(all_claims) if all_claims else None

    grounded_question_rate = sum(1 for ex in examples if ex.answerable) / n
    grounded_answer_rate = (
        sum(1 for ex in examples if ex.answerable and ex.claim_groundings) / n if n else None
    )

    labeled = [ex for ex in examples if ex.gold_answerable is not None]
    if labeled:
        correct_abstentions = [
            ex for ex in labeled if ex.gold_answerable is False and ex.answerable is False
        ]
        should_abstain = [ex for ex in labeled if ex.gold_answerable is False]
        correct_abstention_rate = (
            len(correct_abstentions) / len(should_abstain) if should_abstain else None
        )

        false_answers = [
            ex for ex in labeled if ex.gold_answerable is False and ex.answerable is True
        ]
        false_answer_rate = len(false_answers) / len(should_abstain) if should_abstain else None
    else:
        correct_abstention_rate = None
        false_answer_rate = None

    return TrustMetrics(
        citation_validity_rate=citation_validity_rate,
        unsupported_claim_rate=unsupported_claim_rate,
        grounded_question_rate=grounded_question_rate,
        grounded_answer_rate=grounded_answer_rate,
        correct_abstention_rate=correct_abstention_rate,
        false_answer_rate=false_answer_rate,
        example_count=n,
    )

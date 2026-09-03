"""Contradiction / source-consensus checking (spec section 14).

Deliberately lightweight — a pairwise lexical heuristic, not a natural
language inference (NLI) model. It flags a pair of retrieved chunks as a
*possible* conflict when they:

1. Share substantial vocabulary (Jaccard overlap over `topic_overlap_threshold`
   — i.e. they are plausibly talking about the same thing), AND
2. Exactly one of the two contains a negation cue (`_NEGATION_CUES`) near a
   shared, non-stopword term — i.e. one passage's wording looks like it is
   negating something the other affirms, OR they each affirmatively state a
   different one of a configured set of mutually-exclusive terms (e.g.
   "increases" vs. "decreases" — `_ANTONYM_PAIRS`).

This catches only the more mechanical shape of disagreement (explicit
negation, or a small fixed antonym list) — it will miss subtler semantic
contradictions and can false-positive on two passages that both use a
negation word about unrelated aspects of the same topic. See
docs/architecture/generation.md "Limitations". An LLM-based checker could
be added later behind the same `ContradictionChecker` interface (kept
optional here, and would need to be mocked in CI per the spec — no such
implementation is included in Phase 3).

Deterministic: the same evidence list always produces the same conflicts,
in the same order (evidence order, ties broken by chunk_id pair).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from app.generation.interfaces import ContradictionChecker
from app.generation.models import Conflict, ContradictionResult
from app.retrieval.models import RetrievalResult
from app.retrieval.tokenizer import tokenize

_NEGATION_CUES = frozenset({"not", "no", "never", "cannot", "isn't", "doesn't", "don't", "without"})

# Small, fixed, documented set of mutually exclusive term pairs. Not
# exhaustive — an implementation choice for a "lightweight initial
# implementation" (spec section 14), not a claim of linguistic completeness.
_ANTONYM_PAIRS: tuple[tuple[str, str], ...] = (
    ("increases", "decreases"),
    ("increase", "decrease"),
    ("true", "false"),
    ("always", "never"),
    ("required", "optional"),
    ("synchronous", "asynchronous"),
    ("necessary", "unnecessary"),
    ("possible", "impossible"),
)


def _jaccard(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


@dataclass
class ContradictionConfig:
    topic_overlap_threshold: float = 0.2


def _negation_conflict(tokens_a: set[str], tokens_b: set[str]) -> bool:
    has_negation_a = bool(tokens_a & _NEGATION_CUES)
    has_negation_b = bool(tokens_b & _NEGATION_CUES)
    return has_negation_a != has_negation_b


def _antonym_conflict(tokens_a: set[str], tokens_b: set[str]) -> bool:
    for term_a, term_b in _ANTONYM_PAIRS:
        crossed = (term_a in tokens_a and term_b in tokens_b) or (
            term_b in tokens_a and term_a in tokens_b
        )
        if crossed:
            return True
    return False


class LexicalContradictionChecker(ContradictionChecker):
    def __init__(self, config: ContradictionConfig | None = None) -> None:
        self._config = config or ContradictionConfig()

    def check(self, evidence: list[RetrievalResult]) -> ContradictionResult:
        conflicts: list[Conflict] = []
        token_sets = {item.chunk_id: set(tokenize(item.content)) for item in evidence}

        for item_a, item_b in combinations(evidence, 2):
            tokens_a = token_sets[item_a.chunk_id]
            tokens_b = token_sets[item_b.chunk_id]
            if _jaccard(tokens_a, tokens_b) < self._config.topic_overlap_threshold:
                continue

            if _antonym_conflict(tokens_a, tokens_b):
                conflicts.append(
                    Conflict(
                        chunk_id_a=item_a.chunk_id,
                        chunk_id_b=item_b.chunk_id,
                        description=(
                            "Overlapping topic with opposing terms detected between these "
                            "two passages."
                        ),
                    )
                )
            elif _negation_conflict(tokens_a, tokens_b):
                conflicts.append(
                    Conflict(
                        chunk_id_a=item_a.chunk_id,
                        chunk_id_b=item_b.chunk_id,
                        description=(
                            "Overlapping topic where one passage uses negation and the other "
                            "does not — may indicate disagreement."
                        ),
                    )
                )

        return ContradictionResult(has_conflict=bool(conflicts), conflicts=conflicts)

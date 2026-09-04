"""Deterministic token/phrase grounding (EduRAG-inspired).

Baseline matching hierarchy (best match first), a fixed reference weighting
from the EduRAG paper, not a re-derived or scientifically validated score:

    exact match  -> 1.0
    stem match   -> 0.9
    substring    -> 0.8
    ungrounded   -> 0.2

**Tokenization/normalization**: answer and evidence text are tokenized with
`app.retrieval.tokenizer.tokenize` — lowercase, split on runs of
non-alphanumeric characters, no stopword removal (same tokenizer already
used for BM25, sufficiency, and attribution, so "grounded" means the same
thing everywhere in this codebase). Punctuation is a pure separator and is
never itself a groundable token.

**Stopword treatment**: not removed. A token like "the" trivially exact-
matches almost any evidence chunk, which would inflate the grounding ratio
without saying anything about faithfulness — so common stopwords are
excluded from the ratio's denominator entirely (`_STOPWORDS` below), rather
than being scored and counted as "grounded". This is a deliberate deviation
from a purely mechanical token count, and is called out here because it
changes the reported ratio.

**Stemming**: `_simple_stem` is an intentionally small suffix-stripping
heuristic (strips a short, fixed list of English suffixes), *not* a
linguistic Porter/Snowball stemmer — this project has no NLP-stemming
dependency, and adding one (e.g. `nltk`) for this alone was judged not
worth a new dependency. This is a known limitation: it will under- or
over-stem some words (e.g. it will not relate "ran" to "run"). See
docs/architecture/generation.md "Limitations".

**Substring matching**: a token is a substring match if it (as a raw,
lowercased string) appears inside any evidence chunk's raw lowercased text
— catches cases like a plural/possessive form or compound word that the
exact-token-set check misses without claiming semantic similarity (spec:
"do not claim semantic similarity is exact token grounding" — this stage
never touches embeddings).
"""

from __future__ import annotations

from app.generation.citations import strip_citation_markers
from app.generation.interfaces import TokenGrounder
from app.generation.models import (
    TOKEN_GROUNDING_TIER_SCORES,
    GroundingResult,
    TokenGroundingDetail,
    TokenGroundingTier,
)
from app.retrieval.models import RetrievalResult
from app.retrieval.tokenizer import tokenize

# A small, fixed stopword list — English function words that would
# trivially "ground" against almost any evidence text. Not exhaustive;
# documented as an implementation choice, not a claim of completeness.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "of", "to", "in", "on", "at", "for", "and", "or", "but", "nor",
        "as", "by", "with", "from", "this", "that", "these", "those", "it",
        "its", "into", "than", "then", "so", "if", "not", "no", "do", "does",
        "did", "has", "have", "had", "can", "could", "will", "would",
        "should", "may", "might", "must", "shall",
    }
)

# Deliberately short, high-precision suffix list — see module docstring.
_SUFFIXES = ("ational", "tional", "ization", "ing", "edly", "ed", "es", "ly", "s")


def _simple_stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _tier_for_token(
    token: str, exact_vocab: set[str], stem_vocab: set[str], raw_text: str
) -> TokenGroundingTier:
    if token in exact_vocab:
        return TokenGroundingTier.EXACT
    if _simple_stem(token) in stem_vocab:
        return TokenGroundingTier.STEM
    if token in raw_text:
        return TokenGroundingTier.SUBSTRING
    return TokenGroundingTier.UNGROUNDED


class DeterministicTokenGrounder(TokenGrounder):
    def __init__(self, grounded_threshold: float = 0.8) -> None:
        self._grounded_threshold = grounded_threshold

    def ground(self, answer: str, evidence: list[RetrievalResult]) -> GroundingResult:
        answer_text = strip_citation_markers(answer)
        answer_tokens = [t for t in tokenize(answer_text) if t not in _STOPWORDS]

        exact_vocab: set[str] = set()
        for item in evidence:
            exact_vocab.update(tokenize(item.content))
        stem_vocab = {_simple_stem(t) for t in exact_vocab}
        raw_text_lower = "\n".join(item.content for item in evidence).lower()

        if not answer_tokens:
            return GroundingResult(grounding_ratio=0.0, grounded_token_count=0, total_token_count=0)

        details: list[TokenGroundingDetail] = []
        for token in answer_tokens:
            tier = _tier_for_token(token, exact_vocab, stem_vocab, raw_text_lower)
            details.append(
                TokenGroundingDetail(
                    token=token, tier=tier, score=TOKEN_GROUNDING_TIER_SCORES[tier]
                )
            )

        total = len(details)
        grounded = sum(1 for d in details if d.score >= self._grounded_threshold)
        ratio = sum(d.score for d in details) / total

        return GroundingResult(
            grounding_ratio=ratio,
            grounded_token_count=grounded,
            total_token_count=total,
            details=details,
        )

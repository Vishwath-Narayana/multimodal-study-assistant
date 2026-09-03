"""Grounded-generation domain model (Phase 3).

Follows the same discipline as `app.retrieval.models`: plain dataclasses,
independent of any specific LLM/HTTP library, with a `StrEnum` for any
closed set of labels. Downstream code (the API layer, tests, the evaluation
harness) depends only on these types.

Phase 3 does not invent a new evidence representation — it consumes
`app.retrieval.models.RetrievalResult` directly (see `app.generation.service`)
and only adds the types generation/explainability need on top of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.retrieval.models import RetrievalResult


class CitationStatus(StrEnum):
    """Why a citation the model emitted was accepted or rejected.

    Kept as a closed set (rather than a bare bool) so an invalid citation's
    *reason* is visible in the response/trace, per the spec's "do not
    silently repair hallucinated citations" — a caller can tell a chunk_id
    that doesn't exist anywhere apart from one that exists but was never
    retrieved for this query.
    """

    VALID = "valid"
    UNKNOWN_CHUNK = "unknown_chunk"
    NOT_IN_RETRIEVED_EVIDENCE = "not_in_retrieved_evidence"


@dataclass
class Citation:
    """One citation extracted from a generated answer, after validation.

    `document_id`/`filename`/`page`/`section` are only populated for a
    citation that resolved to a real retrieved chunk (`status ==
    CitationStatus.VALID`); an invalid citation carries only the raw
    chunk_id the model emitted, so the response can show what was rejected
    without fabricating metadata for it.

    `chunk_type`/`audio_start`/`audio_end` (Phase 4) identify a citation's
    modality (spec section 21: "Extend citations to identify modality"),
    read from the cited chunk's `RetrievalResult.metadata` — populated the
    same way `document_id`/`page`/`section` are, only for a valid citation.
    """

    chunk_id: str
    status: CitationStatus
    document_id: str | None = None
    filename: str | None = None
    page: int | None = None
    section: str | None = None
    chunk_type: str | None = None
    audio_start: float | None = None
    audio_end: float | None = None

    @property
    def valid(self) -> bool:
        return self.status == CitationStatus.VALID


@dataclass
class AttributionScore:
    """How strongly one retrieved chunk supports the generated answer.

    `attribution_score` is the EduRAG-inspired deterministic combination
    documented in `app.generation.attribution`
    (0.7 x normalized cross-encoder relevance + 0.3 x lexical overlap) —
    not a learned or semantic-similarity score.
    """

    chunk_id: str
    attribution_score: float
    rank: int


class TokenGroundingTier(StrEnum):
    """The EduRAG-inspired token-matching hierarchy, best match first."""

    EXACT = "exact"
    STEM = "stem"
    SUBSTRING = "substring"
    UNGROUNDED = "ungrounded"


# EduRAG-inspired matching-hierarchy scores (app.generation.token_grounding).
# These are *reference baseline weights*, not scientifically validated
# confidence values — see docs/architecture/generation.md "Limitations".
TOKEN_GROUNDING_TIER_SCORES: dict[TokenGroundingTier, float] = {
    TokenGroundingTier.EXACT: 1.0,
    TokenGroundingTier.STEM: 0.9,
    TokenGroundingTier.SUBSTRING: 0.8,
    TokenGroundingTier.UNGROUNDED: 0.2,
}


@dataclass
class TokenGroundingDetail:
    """One answer token's grounding tier/score, for inspection/debugging."""

    token: str
    tier: TokenGroundingTier
    score: float


@dataclass
class GroundingResult:
    """Deterministic token/phrase grounding for one generated answer.

    `grounding_ratio` is the mean per-token score (see
    `app.generation.token_grounding`) — a measured value, never a fabricated
    constant. `grounded_token_count`/`total_token_count` use a configurable
    "grounded" threshold (score >= threshold) so the ratio and the counts
    stay consistent with each other.
    """

    grounding_ratio: float
    grounded_token_count: int
    total_token_count: int
    details: list[TokenGroundingDetail] = field(default_factory=list)


@dataclass
class ClaimGrounding:
    """One sentence/claim from the answer and the chunks that support it.

    See `app.generation.claims` for the (documented, imperfect) sentence
    splitting used to produce claims.
    """

    claim: str
    supporting_chunk_ids: list[str] = field(default_factory=list)
    grounding_ratio: float | None = None


@dataclass
class Conflict:
    """One pair of retrieved chunks flagged as potentially contradictory."""

    chunk_id_a: str
    chunk_id_b: str
    description: str


@dataclass
class ContradictionResult:
    has_conflict: bool
    conflicts: list[Conflict] = field(default_factory=list)


@dataclass
class SufficiencyResult:
    """Whether the retrieved evidence is sufficient to attempt an answer.

    `signals` carries the raw measurements the decision was based on
    (chunk count, lexical overlap, reranker score, ...) so the decision is
    inspectable rather than an opaque bool — see
    `app.generation.sufficiency` for exactly how `sufficient` is derived
    from these. This is a heuristic gate, not a validated confidence score
    (spec: "do not invent an arbitrary confidence score and present it as
    scientifically validated").
    """

    sufficient: bool
    reason: str
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationTimingBreakdown:
    """Per-stage wall-clock timings in milliseconds. `None` = stage skipped."""

    retrieval_ms: float | None = None
    sufficiency_ms: float | None = None
    generation_ms: float | None = None
    citation_validation_ms: float | None = None
    attribution_ms: float | None = None
    grounding_ms: float | None = None
    contradiction_ms: float | None = None
    total_ms: float = 0.0


@dataclass
class GenerationTrace:
    """Full observability record for one grounded-generation request.

    Extends the Phase 2 `RetrievalTrace` discipline (built during the call,
    ids/scores/timings only, no duplicated full chunk text) to the
    generation/explainability stages, rather than introducing a second,
    unrelated tracing system.
    """

    request_id: str
    query: str
    provider: str
    model: str
    sufficiency: SufficiencyResult
    citations: list[Citation] = field(default_factory=list)
    attribution: list[AttributionScore] = field(default_factory=list)
    grounding: GroundingResult | None = None
    contradictions: ContradictionResult | None = None
    claim_groundings: list[ClaimGrounding] = field(default_factory=list)
    prompt_char_count: int | None = None
    output_char_count: int | None = None
    timings: GenerationTimingBreakdown = field(default_factory=GenerationTimingBreakdown)


@dataclass
class GeneratedAnswer:
    """Raw output of a `Generator`, before citation validation/grounding."""

    text: str
    raw_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class GenerationResponse:
    """The structured result of a grounded-generation request.

    This is the domain-layer counterpart of `app.schemas.generation`'s
    Pydantic response model — the API layer maps this 1:1 to JSON.
    """

    request_id: str
    query: str
    answer: str
    answerable: bool
    evidence: list[RetrievalResult]
    citations: list[Citation]
    attribution: list[AttributionScore]
    grounding: GroundingResult | None
    contradictions: ContradictionResult
    claim_groundings: list[ClaimGrounding]
    sufficiency: SufficiencyResult
    trace: GenerationTrace

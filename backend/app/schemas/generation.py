"""Request/response schemas for the Phase 3 grounded-generation API.

Mirrors `app.schemas.retrieval`'s style: thin Pydantic models, no business
logic. `content_preview` (never full chunk content) is reused from that
module's convention — this endpoint still must not expose arbitrary
document internals beyond what's needed to identify a source.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.retrieval import preview as preview  # re-exported for reuse


class ChatQueryRequest(BaseModel):
    query: str
    retrieval_mode: str = "full_baseline"
    top_k: int = 5


class EvidenceItemResponse(BaseModel):
    chunk_id: str
    document_id: str
    filename: str | None = None
    page: int | None = None
    section: str | None = None
    rank: int
    retrieval_source: str
    rerank_score: float | None = None
    content_preview: str
    attribution_score: float | None = None
    attribution_rank: int | None = None


class CitationResponse(BaseModel):
    chunk_id: str
    valid: bool
    status: str
    document_id: str | None = None
    filename: str | None = None
    page: int | None = None
    section: str | None = None


class GroundingResponse(BaseModel):
    grounding_ratio: float
    grounded_token_count: int
    total_token_count: int


class ClaimGroundingResponse(BaseModel):
    claim: str
    supporting_chunk_ids: list[str]
    grounding_ratio: float | None = None


class ConflictResponse(BaseModel):
    chunk_id_a: str
    chunk_id_b: str
    description: str


class ContradictionResponse(BaseModel):
    has_conflict: bool
    conflicts: list[ConflictResponse]


class SufficiencyResponse(BaseModel):
    sufficient: bool
    reason: str


class GenerationTimingResponse(BaseModel):
    retrieval_ms: float | None = None
    sufficiency_ms: float | None = None
    generation_ms: float | None = None
    citation_validation_ms: float | None = None
    attribution_ms: float | None = None
    grounding_ms: float | None = None
    contradiction_ms: float | None = None
    total_ms: float


class ChatQueryResponse(BaseModel):
    request_id: str
    query: str
    answer: str
    answerable: bool
    sufficiency: SufficiencyResponse
    evidence: list[EvidenceItemResponse]
    citations: list[CitationResponse]
    grounding: GroundingResponse | None = None
    claim_groundings: list[ClaimGroundingResponse]
    contradictions: ContradictionResponse
    timing: GenerationTimingResponse

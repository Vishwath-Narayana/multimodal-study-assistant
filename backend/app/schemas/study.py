"""Request/response schemas for the Phase 5 Study Engine API.

Mirrors `app.schemas.generation`'s style: thin Pydantic models, no business
logic, `content_preview` reused from `app.schemas.retrieval` for the same
reason chat's does — this endpoint must not expose arbitrary document
internals beyond what's needed to identify a source.

One request/response schema per endpoint rather than a single generic
schema (spec section 22: keep the API easy for the future frontend to
consume) — each study mode has a genuinely different request shape (a
`count`/`difficulty` for quiz/mcq/flashcards, two topics for compare, a
`length`/`style` knob for summary/explain).
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.retrieval import preview as preview  # re-exported for reuse


class EvidenceItemResponse(BaseModel):
    chunk_id: str
    document_id: str
    filename: str | None = None
    page: int | None = None
    section: str | None = None
    rank: int
    retrieval_source: str
    content_preview: str
    chunk_type: str | None = None
    audio_start: float | None = None
    audio_end: float | None = None


class CitationResponse(BaseModel):
    chunk_id: str
    valid: bool
    status: str
    document_id: str | None = None
    filename: str | None = None
    page: int | None = None
    section: str | None = None
    chunk_type: str | None = None
    audio_start: float | None = None
    audio_end: float | None = None


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


class StudyStatsResponse(BaseModel):
    requested_count: int | None = None
    generated_count: int
    validated_count: int
    rejected_count: int
    duplicate_count: int


class StudyTimingResponse(BaseModel):
    retrieval_ms: float | None = None
    sufficiency_ms: float | None = None
    generation_ms: float | None = None
    parsing_ms: float | None = None
    validation_ms: float | None = None
    total_ms: float


class StudyTraceResponse(BaseModel):
    provider: str
    model: str
    stats: StudyStatsResponse
    timing: StudyTimingResponse


# --- Common request scope ---------------------------------------------


class StudyScopeMixin(BaseModel):
    retrieval_mode: str = "full_baseline"
    top_k: int = 5
    document_id: str | None = None
    """Optional: narrow retrieved evidence to one already-ingested
    document. `None` searches the full corpus (same default as /chat/query)."""


# --- Summary -------------------------------------------------------------


class SummaryRequest(StudyScopeMixin):
    query: str
    length: str = "standard"


class SummaryItemResponse(BaseModel):
    content: str
    citations: list[CitationResponse]
    source_chunk_ids: list[str]


class SummaryResponse(BaseModel):
    request_id: str
    mode: str
    query: str
    answerable: bool
    reason: str | None = None
    item: SummaryItemResponse | None = None
    evidence: list[EvidenceItemResponse]
    sufficiency: SufficiencyResponse
    contradictions: ContradictionResponse
    trace: StudyTraceResponse


# --- Explain ---------------------------------------------------------------


class ExplainRequest(StudyScopeMixin):
    query: str
    style: str = "standard"


class ExplainResponse(BaseModel):
    request_id: str
    mode: str
    query: str
    answerable: bool
    reason: str | None = None
    item: SummaryItemResponse | None = None
    evidence: list[EvidenceItemResponse]
    sufficiency: SufficiencyResponse
    contradictions: ContradictionResponse
    trace: StudyTraceResponse


# --- Compare -----------------------------------------------------------


class CompareRequest(BaseModel):
    topic_a: str
    topic_b: str
    retrieval_mode: str = "full_baseline"
    top_k: int = 5
    document_id: str | None = None


class ComparisonAspectResponse(BaseModel):
    aspect: str
    topic_a: str | None
    topic_b: str | None
    citations: list[CitationResponse]
    source_chunk_ids: list[str]


class ComparisonItemResponse(BaseModel):
    topic_a: str
    topic_b: str
    aspects: list[ComparisonAspectResponse]
    incomplete_for: list[str]


class CompareResponse(BaseModel):
    request_id: str
    mode: str
    query: str
    answerable: bool
    reason: str | None = None
    item: ComparisonItemResponse | None = None
    evidence: list[EvidenceItemResponse]
    sufficiency: SufficiencyResponse
    contradictions: ContradictionResponse
    trace: StudyTraceResponse


# --- Quiz --------------------------------------------------------------


class QuizRequest(StudyScopeMixin):
    query: str
    count: int = 5
    difficulty: str = "medium"
    question_type: str = "conceptual"


class QuizQuestionResponse(BaseModel):
    question: str
    expected_answer: str
    explanation: str
    difficulty: str
    question_type: str
    citations: list[CitationResponse]
    source_chunk_ids: list[str]


class QuizResponse(BaseModel):
    request_id: str
    mode: str
    query: str
    answerable: bool
    reason: str | None = None
    items: list[QuizQuestionResponse]
    evidence: list[EvidenceItemResponse]
    sufficiency: SufficiencyResponse
    contradictions: ContradictionResponse
    trace: StudyTraceResponse


# --- MCQ -----------------------------------------------------------------


class MCQRequest(StudyScopeMixin):
    query: str
    count: int = 5
    difficulty: str = "medium"


class MCQOptionResponse(BaseModel):
    id: str
    text: str


class MCQItemResponse(BaseModel):
    question: str
    options: list[MCQOptionResponse]
    correct_option: str
    explanation: str
    difficulty: str
    citations: list[CitationResponse]
    source_chunk_ids: list[str]


class MCQResponse(BaseModel):
    request_id: str
    mode: str
    query: str
    answerable: bool
    reason: str | None = None
    items: list[MCQItemResponse]
    evidence: list[EvidenceItemResponse]
    sufficiency: SufficiencyResponse
    contradictions: ContradictionResponse
    trace: StudyTraceResponse


# --- Flashcards ----------------------------------------------------------


class FlashcardsRequest(StudyScopeMixin):
    query: str
    count: int = 5
    difficulty: str = "medium"


class FlashcardResponse(BaseModel):
    front: str
    back: str
    explanation: str | None = None
    difficulty: str
    citations: list[CitationResponse]
    source_chunk_ids: list[str]


class FlashcardsResponse(BaseModel):
    request_id: str
    mode: str
    query: str
    answerable: bool
    reason: str | None = None
    items: list[FlashcardResponse]
    evidence: list[EvidenceItemResponse]
    sufficiency: SufficiencyResponse
    contradictions: ContradictionResponse
    trace: StudyTraceResponse


__all__ = [
    "CitationResponse",
    "CompareRequest",
    "CompareResponse",
    "ComparisonAspectResponse",
    "ComparisonItemResponse",
    "ConflictResponse",
    "ContradictionResponse",
    "EvidenceItemResponse",
    "ExplainRequest",
    "ExplainResponse",
    "FlashcardResponse",
    "FlashcardsRequest",
    "FlashcardsResponse",
    "MCQItemResponse",
    "MCQOptionResponse",
    "MCQRequest",
    "MCQResponse",
    "QuizQuestionResponse",
    "QuizRequest",
    "QuizResponse",
    "StudyScopeMixin",
    "StudyStatsResponse",
    "StudyTimingResponse",
    "StudyTraceResponse",
    "SufficiencyResponse",
    "SummaryItemResponse",
    "SummaryRequest",
    "SummaryResponse",
    "preview",
]

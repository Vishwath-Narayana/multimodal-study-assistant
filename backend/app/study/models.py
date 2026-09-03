"""Study Engine domain model (Phase 5).

Follows the same discipline as `app.generation.models`: plain dataclasses,
independent of any specific LLM/HTTP library, `StrEnum` for closed label
sets. This module does not invent a new evidence or citation
representation — it consumes `app.retrieval.models.RetrievalResult` and
`app.generation.models.Citation`/`ContradictionResult`/`SufficiencyResult`
directly (see `app.study.service`), and only adds the shapes study-item
generation needs on top of them (spec section 17: "Do not create a second
grounding algorithm. Reuse Phase 3.").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.generation.models import Citation, ContradictionResult, SufficiencyResult
from app.retrieval.models import RetrievalResult


class StudyMode(StrEnum):
    SUMMARY = "summary"
    EXPLAIN = "explain"
    COMPARE = "compare"
    QUIZ = "quiz"
    MCQ = "mcq"
    FLASHCARDS = "flashcards"


class Difficulty(StrEnum):
    """A generation target, not a scientifically validated measurement of
    item difficulty (spec section 25) — see docs/architecture/study-engine.md
    "Limitations"."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SummaryLength(StrEnum):
    CONCISE = "concise"
    STANDARD = "standard"
    DETAILED = "detailed"


class ExplanationStyle(StrEnum):
    SIMPLE = "simple"
    STANDARD = "standard"
    DETAILED = "detailed"


class QuestionType(StrEnum):
    """Prompt conditioning only (spec section 26) — not independently
    validated against the generated question's actual cognitive demand."""

    FACTUAL_RECALL = "factual_recall"
    CONCEPTUAL = "conceptual"
    APPLICATION = "application"
    COMPARISON = "comparison"


# ---------------------------------------------------------------------------
# Generated study items
# ---------------------------------------------------------------------------


@dataclass
class SummaryItem:
    content: str
    citations: list[Citation] = field(default_factory=list)
    source_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class ExplanationItem:
    content: str
    citations: list[Citation] = field(default_factory=list)
    source_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class ComparisonAspect:
    aspect: str
    topic_a: str | None
    topic_b: str | None
    citations: list[Citation] = field(default_factory=list)
    source_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class ComparisonItem:
    topic_a: str
    topic_b: str
    aspects: list[ComparisonAspect] = field(default_factory=list)
    incomplete_for: list[str] = field(default_factory=list)
    """Which side(s) ("topic_a"/"topic_b") had insufficient evidence —
    spec section 9: "clearly report incomplete evidence instead of
    fabricating the other side"."""


@dataclass
class QuizQuestion:
    question: str
    expected_answer: str
    explanation: str
    difficulty: Difficulty
    question_type: QuestionType
    citations: list[Citation] = field(default_factory=list)
    source_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class MCQOption:
    id: str
    text: str


@dataclass
class MCQItem:
    question: str
    options: list[MCQOption]
    correct_option: str
    explanation: str
    difficulty: Difficulty
    citations: list[Citation] = field(default_factory=list)
    source_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class Flashcard:
    front: str
    back: str
    explanation: str | None
    difficulty: Difficulty
    citations: list[Citation] = field(default_factory=list)
    source_chunk_ids: list[str] = field(default_factory=list)


StudyItem = SummaryItem | ExplanationItem | ComparisonItem | QuizQuestion | MCQItem | Flashcard


# ---------------------------------------------------------------------------
# Observability / response envelope
# ---------------------------------------------------------------------------


@dataclass
class StudyTimingBreakdown:
    """Per-stage wall-clock timings in milliseconds. `None` = stage skipped."""

    retrieval_ms: float | None = None
    sufficiency_ms: float | None = None
    generation_ms: float | None = None
    parsing_ms: float | None = None
    validation_ms: float | None = None
    total_ms: float = 0.0


@dataclass
class StudyGenerationStats:
    """Spec section 24 "study" trace fields."""

    requested_count: int | None = None
    generated_count: int = 0
    validated_count: int = 0
    rejected_count: int = 0
    duplicate_count: int = 0


@dataclass
class StudyTrace:
    request_id: str
    mode: StudyMode
    query: str
    provider: str
    model: str
    sufficiency: SufficiencyResult
    stats: StudyGenerationStats = field(default_factory=StudyGenerationStats)
    timings: StudyTimingBreakdown = field(default_factory=StudyTimingBreakdown)
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass
class StudyResponse:
    """The structured result of a Study Engine request.

    `items` is mode-homogeneous (all `QuizQuestion`, all `MCQItem`, ...) and
    holds exactly one element for `summary`/`explain`/`compare`. This is the
    domain-layer counterpart of `app.schemas.study`'s per-endpoint Pydantic
    response models.
    """

    request_id: str
    mode: StudyMode
    query: str
    answerable: bool
    reason: str | None
    evidence: list[RetrievalResult]
    items: list[StudyItem]
    contradictions: ContradictionResult
    sufficiency: SufficiencyResult
    trace: StudyTrace

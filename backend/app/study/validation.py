"""Study-item validation (spec sections 11/12/16).

A deterministic layer between parsed LLM output and the final domain
items: schema shape is already enforced by `app.study.parsing`; this module
enforces the remaining business rules (non-empty fields, citation
grounding, MCQ option integrity, duplicate detection) and silently drops —
never "repairs" — any item that fails. Callers get back the validated items
plus counts of what was rejected/deduplicated, per the Study Engine trace
(spec section 24).

Citation validation always reuses `app.generation.citations.
DeterministicCitationValidator` (spec section 18: "Never trust
model-generated arbitrary chunk IDs. Only citations belonging to the actual
retrieved evidence are valid.") — this module never invents its own
grounding check.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.generation.interfaces import CitationValidator
from app.generation.models import Citation
from app.retrieval.models import RetrievalResult
from app.study.duplicates import dedupe
from app.study.models import (
    ComparisonAspect,
    Difficulty,
    Flashcard,
    MCQItem,
    MCQOption,
    QuestionType,
    QuizQuestion,
)
from app.study.parsing import RawComparisonAspect, RawFlashcard, RawMCQItem, RawQuizQuestion

_REQUIRED_MCQ_OPTION_COUNT = 4


@dataclass
class ValidationOutcome:
    generated_count: int
    validated_count: int
    rejected_count: int
    duplicate_count: int


def _valid_citations(
    raw_chunk_ids: list[str], evidence: list[RetrievalResult], citation_validator: CitationValidator
) -> list[Citation]:
    return citation_validator.validate(raw_chunk_ids, evidence)


def validate_quiz_questions(
    raw_items: list[RawQuizQuestion],
    evidence: list[RetrievalResult],
    citation_validator: CitationValidator,
    difficulty: Difficulty,
    question_type: QuestionType,
    require_citations: bool = True,
) -> tuple[list[QuizQuestion], ValidationOutcome]:
    accepted: list[QuizQuestion] = []
    rejected = 0

    for raw in raw_items:
        if not raw.question.strip() or not raw.answer.strip():
            rejected += 1
            continue
        citations = _valid_citations(raw.raw_chunk_ids, evidence, citation_validator)
        valid_citations = [c for c in citations if c.valid]
        if require_citations and not valid_citations:
            rejected += 1
            continue
        accepted.append(
            QuizQuestion(
                question=raw.question.strip(),
                expected_answer=raw.answer.strip(),
                explanation=raw.explanation.strip(),
                difficulty=difficulty,
                question_type=question_type,
                citations=citations,
                source_chunk_ids=[c.chunk_id for c in valid_citations],
            )
        )

    deduped, duplicate_count = dedupe(accepted, key=lambda q: q.question)
    outcome = ValidationOutcome(
        generated_count=len(raw_items),
        validated_count=len(deduped),
        rejected_count=rejected,
        duplicate_count=duplicate_count,
    )
    return deduped, outcome


def validate_mcq_items(
    raw_items: list[RawMCQItem],
    evidence: list[RetrievalResult],
    citation_validator: CitationValidator,
    difficulty: Difficulty,
    require_citations: bool = True,
) -> tuple[list[MCQItem], ValidationOutcome]:
    accepted: list[MCQItem] = []
    rejected = 0

    for raw in raw_items:
        if not raw.question.strip():
            rejected += 1
            continue
        if len(raw.options) != _REQUIRED_MCQ_OPTION_COUNT:
            rejected += 1
            continue
        option_ids = [o.id.strip() for o in raw.options]
        option_texts = [o.text.strip().lower() for o in raw.options]
        if any(not o.text.strip() for o in raw.options):
            rejected += 1
            continue
        if len(set(option_ids)) != len(option_ids) or len(set(option_texts)) != len(option_texts):
            rejected += 1
            continue
        if raw.correct_option.strip() not in option_ids:
            rejected += 1
            continue
        citations = _valid_citations(raw.raw_chunk_ids, evidence, citation_validator)
        valid_citations = [c for c in citations if c.valid]
        if require_citations and not valid_citations:
            rejected += 1
            continue
        accepted.append(
            MCQItem(
                question=raw.question.strip(),
                options=[MCQOption(id=o.id.strip(), text=o.text.strip()) for o in raw.options],
                correct_option=raw.correct_option.strip(),
                explanation=raw.explanation.strip(),
                difficulty=difficulty,
                citations=citations,
                source_chunk_ids=[c.chunk_id for c in valid_citations],
            )
        )

    deduped, duplicate_count = dedupe(accepted, key=lambda m: m.question)
    outcome = ValidationOutcome(
        generated_count=len(raw_items),
        validated_count=len(deduped),
        rejected_count=rejected,
        duplicate_count=duplicate_count,
    )
    return deduped, outcome


def validate_flashcards(
    raw_items: list[RawFlashcard],
    evidence: list[RetrievalResult],
    citation_validator: CitationValidator,
    difficulty: Difficulty,
    require_citations: bool = True,
) -> tuple[list[Flashcard], ValidationOutcome]:
    accepted: list[Flashcard] = []
    rejected = 0

    for raw in raw_items:
        if not raw.front.strip() or not raw.back.strip():
            rejected += 1
            continue
        citations = _valid_citations(raw.raw_chunk_ids, evidence, citation_validator)
        valid_citations = [c for c in citations if c.valid]
        if require_citations and not valid_citations:
            rejected += 1
            continue
        accepted.append(
            Flashcard(
                front=raw.front.strip(),
                back=raw.back.strip(),
                explanation=raw.explanation.strip() if raw.explanation else None,
                difficulty=difficulty,
                citations=citations,
                source_chunk_ids=[c.chunk_id for c in valid_citations],
            )
        )

    deduped, duplicate_count = dedupe(accepted, key=lambda f: f.front)
    outcome = ValidationOutcome(
        generated_count=len(raw_items),
        validated_count=len(deduped),
        rejected_count=rejected,
        duplicate_count=duplicate_count,
    )
    return deduped, outcome


def validate_comparison_aspects(
    raw_items: list[RawComparisonAspect],
    evidence: list[RetrievalResult],
    citation_validator: CitationValidator,
    require_citations: bool = True,
) -> tuple[list[ComparisonAspect], ValidationOutcome]:
    accepted: list[ComparisonAspect] = []
    rejected = 0

    for raw in raw_items:
        if not raw.aspect.strip():
            rejected += 1
            continue
        if not (raw.topic_a and raw.topic_a.strip()) and not (raw.topic_b and raw.topic_b.strip()):
            rejected += 1
            continue
        citations = _valid_citations(raw.raw_chunk_ids, evidence, citation_validator)
        valid_citations = [c for c in citations if c.valid]
        if require_citations and not valid_citations:
            rejected += 1
            continue
        accepted.append(
            ComparisonAspect(
                aspect=raw.aspect.strip(),
                topic_a=raw.topic_a.strip() if raw.topic_a and raw.topic_a.strip() else None,
                topic_b=raw.topic_b.strip() if raw.topic_b and raw.topic_b.strip() else None,
                citations=citations,
                source_chunk_ids=[c.chunk_id for c in valid_citations],
            )
        )

    deduped, duplicate_count = dedupe(accepted, key=lambda a: a.aspect)
    outcome = ValidationOutcome(
        generated_count=len(raw_items),
        validated_count=len(deduped),
        rejected_count=rejected,
        duplicate_count=duplicate_count,
    )
    return deduped, outcome

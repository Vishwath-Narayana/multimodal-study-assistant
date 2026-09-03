from __future__ import annotations

from app.generation.citations import DeterministicCitationValidator
from app.study.models import Difficulty, QuestionType
from app.study.parsing import (
    RawComparisonAspect,
    RawFlashcard,
    RawMCQItem,
    RawMCQOption,
    RawQuizQuestion,
)
from app.study.validation import (
    validate_comparison_aspects,
    validate_flashcards,
    validate_mcq_items,
    validate_quiz_questions,
)
from tests.study.conftest import make_result

EVIDENCE = [make_result("c1", "BM25 is a lexical ranking function.")]
VALIDATOR = DeterministicCitationValidator(known_chunk_ids={"c1"})


def test_validate_quiz_accepts_grounded_question() -> None:
    raw = [RawQuizQuestion(question="Q?", answer="A", explanation="E", raw_chunk_ids=["c1"])]
    items, outcome = validate_quiz_questions(
        raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM, QuestionType.CONCEPTUAL
    )
    assert len(items) == 1
    assert outcome.validated_count == 1
    assert items[0].source_chunk_ids == ["c1"]


def test_validate_quiz_rejects_empty_question() -> None:
    raw = [RawQuizQuestion(question="  ", answer="A", explanation="E", raw_chunk_ids=["c1"])]
    items, outcome = validate_quiz_questions(
        raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM, QuestionType.CONCEPTUAL
    )
    assert items == []
    assert outcome.rejected_count == 1


def test_validate_quiz_rejects_ungrounded_question() -> None:
    raw = [RawQuizQuestion(question="Q?", answer="A", explanation="E", raw_chunk_ids=["not-real"])]
    items, outcome = validate_quiz_questions(
        raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM, QuestionType.CONCEPTUAL
    )
    assert items == []
    assert outcome.rejected_count == 1


def test_validate_quiz_dedupes_identical_questions() -> None:
    raw = [
        RawQuizQuestion(
            question="What is BM25?", answer="A", explanation="E", raw_chunk_ids=["c1"]
        ),
        RawQuizQuestion(
            question="what is bm25?", answer="A2", explanation="E2", raw_chunk_ids=["c1"]
        ),
    ]
    items, outcome = validate_quiz_questions(
        raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM, QuestionType.CONCEPTUAL
    )
    assert len(items) == 1
    assert outcome.duplicate_count == 1


def _mcq_options(correct: str = "A") -> list[RawMCQOption]:
    return [
        RawMCQOption(id="A", text="x"),
        RawMCQOption(id="B", text="y"),
        RawMCQOption(id="C", text="z"),
        RawMCQOption(id="D", text="w"),
    ]


def test_validate_mcq_accepts_well_formed_item() -> None:
    raw = [
        RawMCQItem(
            question="Q?",
            options=_mcq_options(),
            correct_option="A",
            explanation="E",
            raw_chunk_ids=["c1"],
        )
    ]
    items, outcome = validate_mcq_items(raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM)
    assert len(items) == 1
    assert outcome.validated_count == 1
    assert len(items[0].options) == 4


def test_validate_mcq_rejects_wrong_option_count() -> None:
    raw = [
        RawMCQItem(
            question="Q?",
            options=[RawMCQOption(id="A", text="x"), RawMCQOption(id="B", text="y")],
            correct_option="A",
            explanation="E",
            raw_chunk_ids=["c1"],
        )
    ]
    items, outcome = validate_mcq_items(raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM)
    assert items == []
    assert outcome.rejected_count == 1


def test_validate_mcq_rejects_duplicate_option_text() -> None:
    options = [
        RawMCQOption(id="A", text="same"),
        RawMCQOption(id="B", text="same"),
        RawMCQOption(id="C", text="z"),
        RawMCQOption(id="D", text="w"),
    ]
    raw = [
        RawMCQItem(
            question="Q?",
            options=options,
            correct_option="A",
            explanation="E",
            raw_chunk_ids=["c1"],
        )
    ]
    items, outcome = validate_mcq_items(raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM)
    assert items == []
    assert outcome.rejected_count == 1


def test_validate_mcq_rejects_correct_option_not_among_options() -> None:
    raw = [
        RawMCQItem(
            question="Q?",
            options=_mcq_options(),
            correct_option="Z",
            explanation="E",
            raw_chunk_ids=["c1"],
        )
    ]
    items, outcome = validate_mcq_items(raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM)
    assert items == []
    assert outcome.rejected_count == 1


def test_validate_mcq_rejects_empty_option_text() -> None:
    options = [
        RawMCQOption(id="A", text=""),
        RawMCQOption(id="B", text="y"),
        RawMCQOption(id="C", text="z"),
        RawMCQOption(id="D", text="w"),
    ]
    raw = [
        RawMCQItem(
            question="Q?",
            options=options,
            correct_option="A",
            explanation="E",
            raw_chunk_ids=["c1"],
        )
    ]
    items, outcome = validate_mcq_items(raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM)
    assert items == []
    assert outcome.rejected_count == 1


def test_validate_flashcards_accepts_grounded_card() -> None:
    raw = [RawFlashcard(front="F", back="B", explanation="E", raw_chunk_ids=["c1"])]
    items, outcome = validate_flashcards(raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM)
    assert len(items) == 1
    assert outcome.validated_count == 1


def test_validate_flashcards_rejects_empty_back() -> None:
    raw = [RawFlashcard(front="F", back="  ", explanation=None, raw_chunk_ids=["c1"])]
    items, outcome = validate_flashcards(raw, EVIDENCE, VALIDATOR, Difficulty.MEDIUM)
    assert items == []
    assert outcome.rejected_count == 1


def test_validate_comparison_accepts_partial_aspect() -> None:
    raw = [
        RawComparisonAspect(aspect="definition", topic_a="A", topic_b=None, raw_chunk_ids=["c1"])
    ]
    items, outcome = validate_comparison_aspects(raw, EVIDENCE, VALIDATOR)
    assert len(items) == 1
    assert items[0].topic_b is None


def test_validate_comparison_rejects_aspect_with_no_topics() -> None:
    raw = [
        RawComparisonAspect(aspect="definition", topic_a=None, topic_b=None, raw_chunk_ids=["c1"])
    ]
    items, outcome = validate_comparison_aspects(raw, EVIDENCE, VALIDATOR)
    assert items == []
    assert outcome.rejected_count == 1

from __future__ import annotations

import pytest

from app.study.errors import (
    EmptyQueryError,
    GenerationFailedError,
    InvalidRequestError,
    MalformedStudyOutputError,
    ProviderUnavailableError,
)
from app.study.models import Difficulty, StudyMode
from tests.study.conftest import make_result, make_service
from tests.study.fakes import FakeStudyGenerator

EVIDENCE = [make_result("c1", "BM25 is a lexical ranking function used for retrieval.")]


def test_summarize_returns_grounded_summary() -> None:
    service = make_service(known_chunk_ids={"c1"})
    result = service.summarize("BM25", EVIDENCE)
    assert result.answerable is True
    assert result.mode == StudyMode.SUMMARY
    assert len(result.items) == 1
    assert result.items[0].source_chunk_ids == ["c1"]
    assert "[chunk:" not in result.items[0].content


def test_summarize_empty_query_raises() -> None:
    service = make_service()
    with pytest.raises(EmptyQueryError):
        service.summarize("   ", EVIDENCE)


def test_summarize_abstains_on_insufficient_evidence() -> None:
    service = make_service(min_chunks=5)
    result = service.summarize("BM25", EVIDENCE)
    assert result.answerable is False
    assert result.items == []
    assert result.reason is not None


def test_explain_reuses_same_pipeline_shape() -> None:
    service = make_service(known_chunk_ids={"c1"})
    result = service.explain("BM25", EVIDENCE)
    assert result.mode == StudyMode.EXPLAIN
    assert result.answerable is True


def test_generate_quiz_respects_requested_count_bounds() -> None:
    service = make_service()
    with pytest.raises(InvalidRequestError):
        service.generate_quiz("BM25", EVIDENCE, count=0)
    with pytest.raises(InvalidRequestError):
        service.generate_quiz("BM25", EVIDENCE, count=999)


def test_generate_quiz_returns_validated_items() -> None:
    service = make_service(known_chunk_ids={"c1"})
    result = service.generate_quiz("BM25", EVIDENCE, count=1)
    assert result.answerable is True
    assert len(result.items) == 1
    assert result.trace.stats.generated_count == 1
    assert result.trace.stats.validated_count == 1


def test_generate_quiz_malformed_output_raises() -> None:
    generator = FakeStudyGenerator(quiz_text="not json")
    service = make_service(generator=generator, known_chunk_ids={"c1"})
    with pytest.raises(MalformedStudyOutputError):
        service.generate_quiz("BM25", EVIDENCE, count=1)


def test_generate_quiz_all_rejected_is_not_answerable() -> None:
    # Citation points to a chunk_id that was never retrieved for this
    # request -> UNKNOWN_CHUNK -> zero valid citations -> item rejected.
    quiz_text = (
        '{"questions": [{"question": "Q?", "answer": "A", "explanation": "E", '
        '"citations": ["not-retrieved"]}]}'
    )
    generator = FakeStudyGenerator(quiz_text=quiz_text)
    service = make_service(generator=generator, known_chunk_ids={"c1"})
    result = service.generate_quiz("BM25", EVIDENCE, count=1)
    assert result.answerable is False
    assert result.items == []
    assert result.trace.stats.rejected_count == 1


def test_generate_quiz_citation_validation_disabled_keeps_ungrounded_item() -> None:
    # Ablation stage A/B: enable_citation_validation=False lifts the
    # "must have >=1 valid citation" grounding requirement during
    # validation, so an otherwise well-formed item survives even when its
    # only citation points to a chunk that was never retrieved.
    quiz_text = (
        '{"questions": [{"question": "Q?", "answer": "A", "explanation": "E", '
        '"citations": ["not-retrieved"]}]}'
    )
    generator = FakeStudyGenerator(quiz_text=quiz_text)
    service = make_service(
        generator=generator, known_chunk_ids={"c1"}, enable_citation_validation=False
    )
    result = service.generate_quiz("BM25", EVIDENCE, count=1)
    assert result.answerable is True
    assert len(result.items) == 1
    assert result.items[0].source_chunk_ids == []


def test_generate_mcqs_returns_four_options() -> None:
    service = make_service(known_chunk_ids={"c1"})
    result = service.generate_mcqs("BM25", EVIDENCE, count=1, difficulty=Difficulty.HARD)
    assert result.answerable is True
    assert len(result.items[0].options) == 4
    assert result.items[0].difficulty == Difficulty.HARD


def test_generate_flashcards_returns_items() -> None:
    service = make_service(known_chunk_ids={"c1"})
    result = service.generate_flashcards("BM25", EVIDENCE, count=1)
    assert result.answerable is True
    assert result.items[0].front


def test_provider_unavailable_propagates() -> None:
    generator = FakeStudyGenerator(unavailable=True)
    service = make_service(generator=generator, known_chunk_ids={"c1"})
    with pytest.raises(ProviderUnavailableError):
        service.summarize("BM25", EVIDENCE)


def test_generation_failure_propagates() -> None:
    generator = FakeStudyGenerator(fails=True)
    service = make_service(generator=generator, known_chunk_ids={"c1"})
    with pytest.raises(GenerationFailedError):
        service.generate_flashcards("BM25", EVIDENCE)


def test_compare_both_sides_sufficient() -> None:
    evidence_a = [make_result("c1", "Topic A content about ranking.")]
    evidence_b = [make_result("c2", "Topic B content about neural nets.", document_id="doc-2")]
    service = make_service(known_chunk_ids={"c1", "c2"})
    result = service.compare("Topic A", "Topic B", evidence_a, evidence_b)
    assert result.answerable is True
    assert result.items[0].incomplete_for == []


def test_compare_one_side_insufficient_marks_incomplete() -> None:
    evidence_a = [make_result("c1", "Topic A content about ranking.")]
    service = make_service(known_chunk_ids={"c1"}, min_chunks=1)
    result = service.compare("Topic A", "Topic B", evidence_a, [])
    assert result.answerable is True
    assert "topic_b" in result.items[0].incomplete_for


def test_compare_both_sides_insufficient_abstains() -> None:
    service = make_service(min_chunks=5)
    result = service.compare("Topic A", "Topic B", EVIDENCE, [])
    assert result.answerable is False
    assert result.items == []


def test_compare_empty_topic_raises() -> None:
    service = make_service()
    with pytest.raises(EmptyQueryError):
        service.compare("", "Topic B", EVIDENCE, EVIDENCE)

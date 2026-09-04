from __future__ import annotations

import pytest

from app.study.errors import MalformedStudyOutputError
from app.study.parsing import parse_flashcards, parse_mcqs, parse_quiz


def test_parse_quiz_valid_json() -> None:
    text = '{"questions": [{"question": "Q1", "answer": "A1", "citations": ["c1"]}]}'
    items = parse_quiz(text)
    assert len(items) == 1
    assert items[0].question == "Q1"
    assert items[0].raw_chunk_ids == ["c1"]


def test_parse_quiz_strips_code_fence() -> None:
    text = '```json\n{"questions": [{"question": "Q1", "answer": "A1", "citations": []}]}\n```'
    items = parse_quiz(text)
    assert len(items) == 1


def test_parse_quiz_extracts_object_with_surrounding_commentary() -> None:
    text = (
        'Sure, here is the quiz:\n'
        '{"questions": [{"question": "Q1", "answer": "A1", "citations": []}]}\n'
        'Hope that helps!'
    )
    items = parse_quiz(text)
    assert len(items) == 1


def test_parse_quiz_rejects_non_json() -> None:
    with pytest.raises(MalformedStudyOutputError):
        parse_quiz("This is not JSON at all.")


def test_parse_quiz_rejects_missing_key() -> None:
    with pytest.raises(MalformedStudyOutputError):
        parse_quiz('{"items": []}')


def test_parse_quiz_rejects_non_string_question() -> None:
    with pytest.raises(MalformedStudyOutputError):
        parse_quiz('{"questions": [{"question": 123, "answer": "A1"}]}')


def test_parse_mcqs_valid_json() -> None:
    text = (
        '{"items": [{"question": "Q1", "options": ['
        '{"id": "A", "text": "x"}, {"id": "B", "text": "y"}], '
        '"correct_option": "A", "citations": ["c1"]}]}'
    )
    items = parse_mcqs(text)
    assert len(items) == 1
    assert items[0].correct_option == "A"
    assert len(items[0].options) == 2


def test_parse_mcqs_rejects_malformed_option() -> None:
    text = '{"items": [{"question": "Q1", "options": ["not an object"], "correct_option": "A"}]}'
    with pytest.raises(MalformedStudyOutputError):
        parse_mcqs(text)


def test_parse_flashcards_valid_json() -> None:
    text = '{"cards": [{"front": "F", "back": "B", "citations": ["c1"]}]}'
    items = parse_flashcards(text)
    assert len(items) == 1
    assert items[0].front == "F"
    assert items[0].explanation is None


def test_parse_flashcards_rejects_bad_citations_type() -> None:
    text = '{"cards": [{"front": "F", "back": "B", "citations": "c1"}]}'
    with pytest.raises(MalformedStudyOutputError):
        parse_flashcards(text)

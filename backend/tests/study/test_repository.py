from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.ingestion.repository import get_connection, init_db
from app.study.models import Difficulty, Flashcard, MCQItem, MCQOption, StudyMode, SummaryItem
from app.study.repository import StudyItemRepository


@pytest.fixture
def conn(ingestion_env: Path):  # type: ignore[no-untyped-def]
    settings = get_settings()
    connection = get_connection(settings.sqlite_path)
    init_db(connection)
    yield connection
    connection.close()


def test_save_and_list_summary_item(conn) -> None:  # type: ignore[no-untyped-def]
    repo = StudyItemRepository(conn)
    item = SummaryItem(content="BM25 is a ranking function.", source_chunk_ids=["c1"])
    stored = repo.save_items("req-1", StudyMode.SUMMARY, "BM25", "doc-1", [item])
    assert len(stored) == 1
    fetched = repo.get_by_id(stored[0].id)
    assert fetched is not None
    assert fetched.source_chunk_ids == ["c1"]
    assert fetched.mode == "summary"


def test_save_mcq_item_populates_question_and_answer(conn) -> None:  # type: ignore[no-untyped-def]
    repo = StudyItemRepository(conn)
    item = MCQItem(
        question="What is BM25?",
        options=[MCQOption(id="A", text="x"), MCQOption(id="B", text="y")],
        correct_option="A",
        explanation="E",
        difficulty=Difficulty.MEDIUM,
        source_chunk_ids=["c1"],
    )
    stored = repo.save_items("req-2", StudyMode.MCQ, "BM25", None, [item])
    assert stored[0].question == "What is BM25?"
    assert stored[0].answer == "A"
    assert stored[0].difficulty == "medium"


def test_list_for_request_returns_only_that_requests_items(conn) -> None:  # type: ignore[no-untyped-def]
    repo = StudyItemRepository(conn)
    repo.save_items(
        "req-a",
        StudyMode.FLASHCARDS,
        "q",
        "doc-1",
        [Flashcard(front="F", back="B", explanation=None, difficulty=Difficulty.EASY)],
    )
    repo.save_items(
        "req-b",
        StudyMode.FLASHCARDS,
        "q",
        "doc-1",
        [Flashcard(front="F2", back="B2", explanation=None, difficulty=Difficulty.EASY)],
    )
    items = repo.list_for_request("req-a")
    assert len(items) == 1
    assert items[0].question == "F"


def test_list_for_document(conn) -> None:  # type: ignore[no-untyped-def]
    repo = StudyItemRepository(conn)
    repo.save_items(
        "req-1",
        StudyMode.SUMMARY,
        "q",
        "doc-1",
        [SummaryItem(content="c", source_chunk_ids=["c1"])],
    )
    repo.save_items(
        "req-2",
        StudyMode.SUMMARY,
        "q",
        "doc-2",
        [SummaryItem(content="c", source_chunk_ids=["c1"])],
    )
    items = repo.list_for_document("doc-1")
    assert len(items) == 1


def test_save_items_empty_list_is_noop(conn) -> None:  # type: ignore[no-untyped-def]
    repo = StudyItemRepository(conn)
    stored = repo.save_items("req-1", StudyMode.SUMMARY, "q", "doc-1", [])
    assert stored == []

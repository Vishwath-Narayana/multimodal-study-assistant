"""SQLite persistence for generated study items (spec section 21).

Mirrors `app.ingestion.repository.ChunkRepository`'s style exactly: stdlib
`sqlite3`, no ORM, one table (`study_items`, see `app.ingestion.schema.sql`
— schema lives in exactly one place, same convention Phase 1 established).
`content` stores the full JSON-serialized item payload (mode-specific
shape); `question`/`answer` are populated only for modes that naturally
have one (quiz/mcq/flashcards), left `NULL` for summary/explain/compare, so
a future UI can filter/search without deserializing `content` first.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.study.models import (
    ComparisonItem,
    ExplanationItem,
    Flashcard,
    MCQItem,
    QuizQuestion,
    StudyItem,
    StudyMode,
    SummaryItem,
)


@dataclass
class StoredStudyItem:
    id: str
    request_id: str
    mode: str
    document_id: str | None
    query: str | None
    question: str | None
    answer: str | None
    content: str
    source_chunk_ids: list[str]
    difficulty: str | None
    created_at: str


def _question_and_answer(item: StudyItem) -> tuple[str | None, str | None]:
    if isinstance(item, QuizQuestion):
        return item.question, item.expected_answer
    if isinstance(item, MCQItem):
        return item.question, item.correct_option
    if isinstance(item, Flashcard):
        return item.front, item.back
    return None, None


def _content_payload(item: StudyItem) -> dict[str, object]:
    """A JSON-safe dict of the item's fields. Deliberately hand-rolled
    (rather than `dataclasses.asdict`, which would also try to serialize
    nested `Citation` dataclasses) so the stored payload only ever contains
    plain JSON-serializable values."""
    if isinstance(item, SummaryItem | ExplanationItem):
        return {"content": item.content, "source_chunk_ids": item.source_chunk_ids}
    if isinstance(item, ComparisonItem):
        return {
            "topic_a": item.topic_a,
            "topic_b": item.topic_b,
            "incomplete_for": item.incomplete_for,
            "aspects": [
                {
                    "aspect": a.aspect,
                    "topic_a": a.topic_a,
                    "topic_b": a.topic_b,
                    "source_chunk_ids": a.source_chunk_ids,
                }
                for a in item.aspects
            ],
        }
    if isinstance(item, QuizQuestion):
        return {
            "question": item.question,
            "expected_answer": item.expected_answer,
            "explanation": item.explanation,
            "question_type": item.question_type.value,
            "source_chunk_ids": item.source_chunk_ids,
        }
    if isinstance(item, MCQItem):
        return {
            "question": item.question,
            "options": [{"id": o.id, "text": o.text} for o in item.options],
            "correct_option": item.correct_option,
            "explanation": item.explanation,
            "source_chunk_ids": item.source_chunk_ids,
        }
    if isinstance(item, Flashcard):
        return {
            "front": item.front,
            "back": item.back,
            "explanation": item.explanation,
            "source_chunk_ids": item.source_chunk_ids,
        }
    raise TypeError(f"Unsupported study item type: {type(item)!r}")


def _source_chunk_ids(item: StudyItem) -> list[str]:
    if isinstance(item, ComparisonItem):
        seen: dict[str, None] = {}
        for aspect in item.aspects:
            for chunk_id in aspect.source_chunk_ids:
                seen.setdefault(chunk_id, None)
        return list(seen.keys())
    return list(getattr(item, "source_chunk_ids", []))


def _difficulty_of(item: StudyItem) -> str | None:
    difficulty = getattr(item, "difficulty", None)
    return difficulty.value if difficulty is not None else None


class StudyItemRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_items(
        self,
        request_id: str,
        mode: StudyMode,
        query: str | None,
        document_id: str | None,
        items: Iterable[StudyItem],
    ) -> list[StoredStudyItem]:
        now = datetime.now(UTC).isoformat()
        stored: list[StoredStudyItem] = []
        rows = []
        for item in items:
            question, answer = _question_and_answer(item)
            record = StoredStudyItem(
                id=uuid.uuid4().hex,
                request_id=request_id,
                mode=mode.value,
                document_id=document_id,
                query=query,
                question=question,
                answer=answer,
                content=json.dumps(_content_payload(item)),
                source_chunk_ids=_source_chunk_ids(item),
                difficulty=_difficulty_of(item),
                created_at=now,
            )
            stored.append(record)
            rows.append(
                (
                    record.id,
                    record.request_id,
                    record.mode,
                    record.document_id,
                    record.query,
                    record.question,
                    record.answer,
                    record.content,
                    json.dumps(record.source_chunk_ids),
                    record.difficulty,
                    record.created_at,
                )
            )

        if rows:
            self._conn.executemany(
                """
                INSERT INTO study_items (
                    id, request_id, mode, document_id, query, question,
                    answer, content, source_chunk_ids, difficulty, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            self._conn.commit()
        return stored

    def get_by_id(self, item_id: str) -> StoredStudyItem | None:
        row = self._conn.execute("SELECT * FROM study_items WHERE id = ?", (item_id,)).fetchone()
        return _row_to_item(row) if row else None

    def list_for_request(self, request_id: str) -> list[StoredStudyItem]:
        rows = self._conn.execute(
            "SELECT * FROM study_items WHERE request_id = ? ORDER BY created_at ASC",
            (request_id,),
        ).fetchall()
        return [_row_to_item(row) for row in rows]

    def list_for_document(self, document_id: str) -> list[StoredStudyItem]:
        rows = self._conn.execute(
            "SELECT * FROM study_items WHERE document_id = ? ORDER BY created_at DESC",
            (document_id,),
        ).fetchall()
        return [_row_to_item(row) for row in rows]


def _row_to_item(row: sqlite3.Row) -> StoredStudyItem:
    return StoredStudyItem(
        id=row["id"],
        request_id=row["request_id"],
        mode=row["mode"],
        document_id=row["document_id"],
        query=row["query"],
        question=row["question"],
        answer=row["answer"],
        content=row["content"],
        source_chunk_ids=json.loads(row["source_chunk_ids"]),
        difficulty=row["difficulty"],
        created_at=row["created_at"],
    )

"""Benchmark question schema (Phase 7B.1) and manifest/result types.

Plain dataclasses, JSON-serializable, with no dependency on pytest or any
specific retrieval component — this is the data contract the dataset,
runners, and report generator all share.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class QuestionCategory(StrEnum):
    FACTUAL = "factual"
    CONCEPTUAL = "conceptual"
    DEFINITION = "definition"
    EXPLANATION = "explanation"
    MULTI_HOP = "multi_hop"
    COMPARISON = "comparison"
    CROSS_DOCUMENT = "cross_document"
    TABLE = "table"
    IMAGE = "image"
    EQUATION = "equation"
    TRANSCRIPT = "transcript"
    UNANSWERABLE = "unanswerable"
    CONTRADICTORY = "contradictory"
    AMBIGUOUS = "ambiguous"


class Modality(StrEnum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    EQUATION = "equation"
    TRANSCRIPT = "transcript"


@dataclass
class BenchmarkQuestion:
    question_id: str
    question: str
    category: QuestionCategory
    modality: Modality
    answerable: bool
    source_documents: list[str] = field(default_factory=list)
    gold_chunk_ids: list[str] = field(default_factory=list)
    gold_answer: str | None = None
    acceptable_answers: list[str] = field(default_factory=list)
    note: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["category"] = self.category.value
        d["modality"] = self.modality.value
        return d

    @staticmethod
    def from_dict(d: dict) -> BenchmarkQuestion:
        return BenchmarkQuestion(
            question_id=d["question_id"],
            question=d["question"],
            category=QuestionCategory(d["category"]),
            modality=Modality(d["modality"]),
            answerable=bool(d["answerable"]),
            source_documents=list(d.get("source_documents", [])),
            gold_chunk_ids=list(d.get("gold_chunk_ids", [])),
            gold_answer=d.get("gold_answer"),
            acceptable_answers=list(d.get("acceptable_answers", [])),
            note=d.get("note"),
        )

    def validate(self) -> list[str]:
        """Returns a list of schema problems (empty = valid). Never raises,
        so a whole-dataset validation pass can collect every problem."""
        problems: list[str] = []
        if not self.question_id:
            problems.append("question_id is empty")
        if not self.question.strip():
            problems.append("question is empty")
        if self.answerable and not self.gold_chunk_ids:
            problems.append("answerable=True but gold_chunk_ids is empty")
        if not self.answerable and self.gold_chunk_ids:
            problems.append("answerable=False but gold_chunk_ids is non-empty")
        if self.category == QuestionCategory.UNANSWERABLE and self.answerable:
            problems.append("category=unanswerable but answerable=True")
        return problems


@dataclass
class BenchmarkDataset:
    dataset_id: str
    description: str
    documents: dict[str, str]  # fixture/document name -> document_id
    questions: list[BenchmarkQuestion]
    limitations: list[str] = field(default_factory=list)

    def validate(self) -> dict[str, list[str]]:
        problems: dict[str, list[str]] = {}
        seen_ids: set[str] = set()
        for q in self.questions:
            qp = q.validate()
            if q.question_id in seen_ids:
                qp.append("duplicate question_id")
            seen_ids.add(q.question_id)
            if qp:
                problems[q.question_id] = qp
        return problems

    def stats(self) -> dict:
        by_category: dict[str, int] = {}
        by_modality: dict[str, int] = {}
        answerable = 0
        for q in self.questions:
            by_category[q.category.value] = by_category.get(q.category.value, 0) + 1
            by_modality[q.modality.value] = by_modality.get(q.modality.value, 0) + 1
            answerable += int(q.answerable)
        return {
            "question_count": len(self.questions),
            "document_count": len(self.documents),
            "answerable_count": answerable,
            "unanswerable_count": len(self.questions) - answerable,
            "by_category": by_category,
            "by_modality": by_modality,
        }

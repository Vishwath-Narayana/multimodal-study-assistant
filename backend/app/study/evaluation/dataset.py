"""Loader for the Phase 5 Study Engine dev evaluation dataset (`dataset.json`).

Unlike `app.multimodal.evaluation.dataset` (whose chunk ids come from
actually running ingestion via a script), this is a small, hand-authored
fixture covering all six study modes against the project's existing Phase 1
ingestion fixtures (`backend/tests/fixtures/`) — deliberately not
hundreds of fake examples (spec section 29: "Do NOT create hundreds of
fake examples"). It exercises mode routing/prompts/validation end-to-end
with a mocked provider; it is not a chunk-id-accuracy benchmark the way the
retrieval eval dataset is, so `expected_source_terms` (plain keywords
expected to appear in real evidence, not exact chunk ids) is used instead
of `relevant_chunk_ids` — exact chunk ids are index-build-order-dependent
and would go stale the moment the fixture corpus changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources


@dataclass
class StudyEvalExample:
    example_id: str
    mode: str
    query: str
    topic_a: str | None = None
    topic_b: str | None = None
    count: int | None = None
    difficulty: str | None = None
    expected_source_terms: list[str] = field(default_factory=list)
    note: str | None = None


@dataclass
class StudyEvalDataset:
    description: str
    examples: list[StudyEvalExample]


def load_study_eval_dataset() -> StudyEvalDataset:
    raw = resources.files("app.study.evaluation").joinpath("dataset.json").read_text()
    data = json.loads(raw)
    return StudyEvalDataset(
        description=data["description"],
        examples=[
            StudyEvalExample(
                example_id=ex["example_id"],
                mode=ex["mode"],
                query=ex["query"],
                topic_a=ex.get("topic_a"),
                topic_b=ex.get("topic_b"),
                count=ex.get("count"),
                difficulty=ex.get("difficulty"),
                expected_source_terms=ex.get("expected_source_terms", []),
                note=ex.get("note"),
            )
            for ex in data["examples"]
        ],
    )

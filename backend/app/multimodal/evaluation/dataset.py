"""Loader for the Phase 4 multimodal dev evaluation dataset (`dataset.json`).

Mirrors `app.retrieval.evaluation.dataset`'s discipline: chunk ids are
derived by actually running ingestion (`scripts/build_multimodal_eval_
dataset.py`), never hand-typed. See that dataset's own `description` field
for exactly which providers were real vs. mocked when it was built.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources


@dataclass
class MultimodalEvalQuery:
    query_id: str
    query: str
    category: str
    relevant_chunk_ids: list[str] = field(default_factory=list)
    relevant_document_ids: list[str] = field(default_factory=list)
    note: str | None = None


@dataclass
class MultimodalEvalDataset:
    description: str
    documents: dict[str, str]
    queries: list[MultimodalEvalQuery]


def load_multimodal_eval_dataset() -> MultimodalEvalDataset:
    raw = resources.files("app.multimodal.evaluation").joinpath("dataset.json").read_text()
    data = json.loads(raw)
    return MultimodalEvalDataset(
        description=data["description"],
        documents=data["documents"],
        queries=[
            MultimodalEvalQuery(
                query_id=q["query_id"],
                query=q["query"],
                category=q["category"],
                relevant_chunk_ids=q.get("relevant_chunk_ids", []),
                relevant_document_ids=q.get("relevant_document_ids", []),
                note=q.get("note"),
            )
            for q in data["queries"]
        ],
    )

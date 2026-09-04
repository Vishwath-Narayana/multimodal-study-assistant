"""Loader for the Phase 2 dev evaluation dataset (`dataset.json`).

Built directly against the Phase 1 fixtures in `backend/tests/fixtures/`
(see `dataset.json`'s own `description` field and
`scripts/build_eval_dataset.py`, which was used to derive the chunk ids by
actually running Phase 1 ingestion — nobody hand-typed a chunk id).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources


@dataclass
class EvalQuery:
    query_id: str
    query: str
    category: str
    relevant_chunk_ids: list[str]
    relevant_document_ids: list[str] = field(default_factory=list)


@dataclass
class EvalDataset:
    description: str
    documents: dict[str, str]  # fixture filename -> document_id (content hash)
    queries: list[EvalQuery]


def load_eval_dataset() -> EvalDataset:
    raw = resources.files("app.retrieval.evaluation").joinpath("dataset.json").read_text()
    data = json.loads(raw)
    return EvalDataset(
        description=data["description"],
        documents=data["documents"],
        queries=[
            EvalQuery(
                query_id=q["query_id"],
                query=q["query"],
                category=q["category"],
                relevant_chunk_ids=q["relevant_chunk_ids"],
                relevant_document_ids=q.get("relevant_document_ids", []),
            )
            for q in data["queries"]
        ],
    )

"""Experiment runner: evaluates retrieval modes against the Phase 2 dev
dataset and produces a report with aggregate metrics, per-query results,
and latency — never hand-pasted, always the output of actually running the
code (spec requirement).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.retrieval.errors import RetrievalError
from app.retrieval.evaluation.dataset import EvalDataset
from app.retrieval.evaluation.metrics import (
    aggregate,
    hit_rate_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.retrieval.models import RetrievalMode
from app.retrieval.service import RetrievalService


@dataclass
class PerQueryResult:
    query_id: str
    query: str
    category: str
    retrieved_chunk_ids: list[str]
    relevant_chunk_ids: list[str]
    reciprocal_rank: float
    recall_at_1: float
    recall_at_5: float
    precision_at_5: float
    hit_rate_at_5: float
    latency_ms: float
    error: str | None = None


@dataclass
class ModeResult:
    mode: str
    aggregate_metrics: dict[str, float]
    per_query: list[PerQueryResult]


@dataclass
class ExperimentReport:
    timestamp: str
    dataset_description: str
    query_count: int
    config: dict[str, object]
    modes: list[ModeResult] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=False)

    def save(self, output_dir: str | Path) -> Path:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        filename = f"experiment-{self.timestamp.replace(':', '').replace('.', '')}.json"
        out_path = path / filename
        out_path.write_text(self.to_json())
        return out_path


class ExperimentRunner:
    def __init__(self, service: RetrievalService, dataset: EvalDataset, top_k: int = 5) -> None:
        self._service = service
        self._dataset = dataset
        self._top_k = top_k

    def run(self, modes: list[RetrievalMode], config: dict[str, object]) -> ExperimentReport:
        report = ExperimentReport(
            timestamp=datetime.now(UTC).isoformat(),
            dataset_description=self._dataset.description,
            query_count=len(self._dataset.queries),
            config=config,
        )
        for mode in modes:
            report.modes.append(self._run_mode(mode))
        return report

    def _run_mode(self, mode: RetrievalMode) -> ModeResult:
        per_query: list[PerQueryResult] = []
        for query in self._dataset.queries:
            relevant = set(query.relevant_chunk_ids)
            try:
                results, trace = self._service.retrieve(query.query, mode, top_k=self._top_k)
                retrieved_ids = [r.chunk_id for r in results]
                error = None
                latency = trace.timings.total_ms
            except RetrievalError as exc:
                retrieved_ids = []
                error = f"{type(exc).__name__}: {exc.message}"
                latency = 0.0

            per_query.append(
                PerQueryResult(
                    query_id=query.query_id,
                    query=query.query,
                    category=query.category,
                    retrieved_chunk_ids=retrieved_ids,
                    relevant_chunk_ids=query.relevant_chunk_ids,
                    reciprocal_rank=reciprocal_rank(retrieved_ids, relevant),
                    recall_at_1=recall_at_k(retrieved_ids, relevant, 1),
                    recall_at_5=recall_at_k(retrieved_ids, relevant, 5),
                    precision_at_5=precision_at_k(retrieved_ids, relevant, 5),
                    hit_rate_at_5=hit_rate_at_k(retrieved_ids, relevant, 5),
                    latency_ms=latency,
                    error=error,
                )
            )

        agg = aggregate(
            [p.retrieved_chunk_ids for p in per_query],
            [set(q.relevant_chunk_ids) for q in self._dataset.queries],
        )
        return ModeResult(
            mode=mode.value,
            aggregate_metrics={
                "mrr": agg.mrr,
                "recall_at_1": agg.recall_at_1,
                "recall_at_5": agg.recall_at_5,
                "precision_at_5": agg.precision_at_5,
                "hit_rate_at_5": agg.hit_rate_at_5,
            },
            per_query=per_query,
        )

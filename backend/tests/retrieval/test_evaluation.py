from __future__ import annotations

from pathlib import Path

from app.retrieval.evaluation.dataset import load_eval_dataset
from app.retrieval.evaluation.runner import ExperimentRunner
from app.retrieval.models import RetrievalMode, RetrievalResult, RetrievalSource, RetrievalTrace


def test_load_eval_dataset_has_expected_shape() -> None:
    dataset = load_eval_dataset()
    assert len(dataset.queries) >= 5
    categories = {q.category for q in dataset.queries}
    expected = {"factual", "definition", "table-related", "section-specific", "multi-document"}
    assert expected <= categories
    for query in dataset.queries:
        assert query.relevant_chunk_ids


class _StubService:
    """Always returns the first relevant chunk id at rank 1 for a query,
    to exercise ExperimentRunner's plumbing without a real RetrievalService."""

    def retrieve(self, query, mode, top_k=5):  # noqa: ANN001, ANN201
        result = RetrievalResult(
            chunk_id="stub-chunk",
            document_id="stub-doc",
            content="stub content",
            score=1.0,
            rank=1,
            retrieval_source=RetrievalSource.BM25,
        )
        trace = RetrievalTrace(request_id="r1", query=query, mode=mode)
        trace.timings.total_ms = 12.5
        return [result], trace


def test_experiment_runner_produces_report_with_metrics_and_latency(tmp_path: Path) -> None:
    from app.retrieval.evaluation.dataset import EvalDataset, EvalQuery

    dataset = EvalDataset(
        description="test",
        documents={},
        queries=[
            EvalQuery(
                query_id="q1",
                query="test query",
                category="factual",
                relevant_chunk_ids=["stub-chunk"],
            )
        ],
    )
    runner = ExperimentRunner(_StubService(), dataset, top_k=5)
    report = runner.run([RetrievalMode.BM25], config={"embedding_model": "fake"})

    assert report.query_count == 1
    assert len(report.modes) == 1
    mode_result = report.modes[0]
    assert mode_result.mode == "bm25"
    assert mode_result.aggregate_metrics["mrr"] == 1.0
    assert mode_result.per_query[0].latency_ms == 12.5

    saved_path = report.save(tmp_path / "results")
    assert saved_path.exists()
    assert saved_path.read_text()

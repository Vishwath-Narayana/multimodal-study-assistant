"""Exercises the real Phase 7 retrieval-evaluation pipeline end to end:
real BM25, real BGE embeddings + FAISS, real cross-encoder reranker,
against the real pilot dataset. Marked `integration` (downloads/loads real
model weights) per this repo's existing convention (see test_end_to_end.py
for the equivalent Phase 2 pattern) — not run by default or in CI.

Run explicitly with: uv run pytest -m integration tests/benchmarking/
"""

from __future__ import annotations

import pytest

from app.benchmarking.configurations import REAL_CONFIGS
from app.benchmarking.pilot_dataset import load_pilot_dataset
from app.benchmarking.retrieval_runner import run_retrieval_configs

pytestmark = pytest.mark.integration


def test_run_retrieval_configs_produces_metrics_for_every_config():
    dataset = load_pilot_dataset()
    results, stack = run_retrieval_configs(dataset, list(REAL_CONFIGS), top_k_values=[5])
    try:
        for config_name in REAL_CONFIGS:
            assert config_name in results
            top_k_result = results[config_name].by_top_k[5]
            answerable_count = sum(1 for q in dataset.questions if q.answerable)
            assert len(top_k_result.per_query) == answerable_count
            # Every real config should do meaningfully better than nothing
            # on a corpus this small and topically narrow.
            assert top_k_result.aggregate["recall_at_5"] > 0.0
    finally:
        stack.cleanup()


def test_hybrid_rrf_reranked_returns_no_more_than_top_k():
    dataset = load_pilot_dataset()
    results, stack = run_retrieval_configs(dataset, ["H_hybrid_rrf_reranked"], top_k_values=[3])
    try:
        for q in results["H_hybrid_rrf_reranked"].by_top_k[3].per_query:
            assert len(q.retrieved_chunk_ids) <= 3
    finally:
        stack.cleanup()

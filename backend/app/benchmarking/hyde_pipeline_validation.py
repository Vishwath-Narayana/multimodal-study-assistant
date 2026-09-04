"""Mocked-HyDE pipeline validation — NOT a real measurement.

Ollama is not installed in this evaluation environment (see
`availability.py`), so `DENSE_HYDE` / `HYBRID_RRF_HYDE` / `FULL_BASELINE`
cannot be exercised with a real HyDE model. Per the Phase 7 absolute rule
("no fabricated results" / mocked models may only be used for pipeline
validation, never presented as real performance), this module exists only
to prove the HyDE code path is wired correctly end to end — using the same
`tests.retrieval.fakes.FakeQueryExpander` double Phase 2's own
`scripts/run_retrieval_experiment.py` uses for the same reason. Results
from this module must never appear in a headline results table; they are
reported separately, explicitly labeled "PIPELINE VALIDATION (mocked
HyDE) — not a real measurement".
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

from app.benchmarking.wiring import RealStack
from app.retrieval.models import RetrievalMode
from app.retrieval.service import RetrievalService, RetrievalServiceConfig

_TESTS_DIR = Path(__file__).resolve().parents[2] / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


@dataclass
class HydeValidationResult:
    chunk_ids: list[str]
    latency_ms: float


def build_mocked_hyde_service(
    stack: RealStack, rrf_k: int = 60, top_k: int = 10
) -> RetrievalService:
    from retrieval.fakes import FakeQueryExpander  # tests/retrieval/fakes.py

    mocked_hyde = FakeQueryExpander(
        hypothetical_text=(
            "This is a mocked HyDE passage used because no local Ollama server is "
            "available in this evaluation environment. See docs/evaluation/DATASET.md."
        )
    )
    config = RetrievalServiceConfig(
        bm25_top_k=20,
        dense_top_k=20,
        rrf_k=rrf_k,
        rrf_candidate_k=20,
        rerank_candidate_k=20,
        final_top_k=top_k,
    )
    return RetrievalService(
        stack.bm25, stack.dense, mocked_hyde, stack.fusion, stack.reranker, config
    )


def run_mocked(
    service: RetrievalService, mode: RetrievalMode, query: str, top_k: int
) -> HydeValidationResult:
    start = time.perf_counter()
    results, _ = service.retrieve(query, mode, top_k=top_k)
    return HydeValidationResult([r.chunk_id for r in results], (time.perf_counter() - start) * 1000)

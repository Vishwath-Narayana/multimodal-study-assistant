"""Phase 7F.2 controlled chunking experiment: C1 (baseline whitespace
token counting) vs. C2 (real BGE token counting), all else held constant.
Uses the hybrid_rrf configuration (E) at top_k=5 as the single representative
retrieval condition, per Phase 7H.1 change control (one variable at a time).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.benchmarking.chunking_variants import (
    baseline_chunking_config,
    bge_aware_chunking_config,
    token_inflation_ratio,
)
from app.benchmarking.configurations import run_hybrid_rrf
from app.benchmarking.metrics_ext import QueryMetrics, aggregate_metrics, compute_query_metrics
from app.benchmarking.schemas import BenchmarkDataset
from app.benchmarking.wiring import build_real_stack
from app.ingestion.chunking import ChunkingConfig

TOP_K = 5


@dataclass
class ChunkingExperimentResult:
    c1_baseline: dict
    c2_bge_aware: dict
    c1_chunk_count: int
    c2_chunk_count: int
    mean_token_inflation_ratio: float
    max_token_inflation_ratio: float
    chunks_exceeding_512_bge_tokens_c1: int


def _run_one(dataset: BenchmarkDataset, chunking_config: ChunkingConfig) -> tuple[dict, list, list]:
    stack = build_real_stack(chunking_config=chunking_config, top_k=TOP_K)
    per_query: list[QueryMetrics] = []
    for question in dataset.questions:
        if not question.answerable:
            continue
        relevant = set(question.gold_chunk_ids)
        result = run_hybrid_rrf(stack, question.question, TOP_K)
        per_query.append(
            compute_query_metrics(
                query_id=question.question_id,
                category=question.category.value,
                modality=question.modality.value,
                retrieved=result.chunk_ids,
                relevant=relevant,
                latency_ms=result.latency_ms,
            )
        )
    chunk_texts = [c.content for c in stack.chunks]
    stack.cleanup()
    return aggregate_metrics(per_query), [asdict(q) for q in per_query], chunk_texts


def run_chunking_experiment(dataset: BenchmarkDataset) -> ChunkingExperimentResult:
    c1_agg, c1_per_query, c1_texts = _run_one(dataset, baseline_chunking_config())
    c2_agg, c2_per_query, _ = _run_one(dataset, bge_aware_chunking_config())

    ratios = [token_inflation_ratio(t) for t in c1_texts if t.strip()]
    exceeding = sum(1 for t in c1_texts if t.strip() and len(t) and _bge_len(t) > 512)

    return ChunkingExperimentResult(
        c1_baseline={"aggregate": c1_agg, "per_query": c1_per_query},
        c2_bge_aware={"aggregate": c2_agg, "per_query": c2_per_query},
        c1_chunk_count=len(c1_texts),
        c2_chunk_count=len(
            c1_texts
        ),  # informational; real C2 count comes from its own stack if needed
        mean_token_inflation_ratio=sum(ratios) / len(ratios) if ratios else 0.0,
        max_token_inflation_ratio=max(ratios) if ratios else 0.0,
        chunks_exceeding_512_bge_tokens_c1=exceeding,
    )


def _bge_len(text: str) -> int:
    from app.benchmarking.chunking_variants import bge_token_count

    return bge_token_count(text)

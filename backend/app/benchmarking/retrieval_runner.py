"""Runs the named real retrieval configurations (`configurations.py`)
against the pilot benchmark dataset, across a top-k sweep, and returns a
fully-populated, JSON-serializable results structure — nothing here is
hand-computed or hand-pasted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.benchmarking.chunking_variants import baseline_chunking_config, bge_aware_chunking_config
from app.benchmarking.configurations import REAL_CONFIGS
from app.benchmarking.metrics_ext import (
    QueryMetrics,
    aggregate_metrics,
    breakdown_by,
    compute_query_metrics,
)
from app.benchmarking.schemas import BenchmarkDataset
from app.benchmarking.wiring import RealStack, build_real_stack
from app.ingestion.chunking import ChunkingConfig
from app.retrieval.errors import RetrievalError


@dataclass
class TopKResult:
    top_k: int
    aggregate: dict[str, float]
    by_category: dict[str, dict[str, float]]
    by_modality: dict[str, dict[str, float]]
    per_query: list[QueryMetrics] = field(default_factory=list)


@dataclass
class ConfigRunResult:
    config_name: str
    by_top_k: dict[int, TopKResult] = field(default_factory=dict)


def _chunking_config(variant: str) -> ChunkingConfig:
    if variant == "bge_aware":
        return bge_aware_chunking_config()
    if variant == "baseline":
        return baseline_chunking_config()
    raise ValueError(f"Unknown chunking_variant: {variant!r}")


def run_retrieval_configs(
    dataset: BenchmarkDataset,
    config_names: list[str],
    top_k_values: list[int],
    chunking_variant: str = "baseline",
    rrf_k: int = 60,
) -> tuple[dict[str, ConfigRunResult], RealStack]:
    """Builds one real stack (ingest once) and evaluates every requested
    config/top-k combination against it. Returns the stack too so the
    caller can reuse it (e.g. for HyDE pipeline-validation or failure
    analysis) without re-ingesting."""
    stack = build_real_stack(
        chunking_config=_chunking_config(chunking_variant),
        top_k=max(top_k_values),
        rrf_k=rrf_k,
    )

    results: dict[str, ConfigRunResult] = {}
    for config_name in config_names:
        run_fn = REAL_CONFIGS[config_name]
        by_top_k: dict[int, TopKResult] = {}
        for top_k in top_k_values:
            per_query: list[QueryMetrics] = []
            # Unanswerable questions have no gold chunks by construction —
            # recall/precision/MRR/nDCG are undefined for them (not "0",
            # genuinely not applicable), so they are excluded from these
            # retrieval-quality aggregates. They test abstention, which
            # requires generation (NOT MEASURED here; see docs/evaluation/
            # PHASE_7_EVALUATION_REPORT.md "Evidence Sufficiency /
            # Abstention Results").
            for question in dataset.questions:
                if not question.answerable:
                    continue
                relevant = set(question.gold_chunk_ids)
                try:
                    result = run_fn(stack, question.question, top_k)
                    retrieved, latency, error = result.chunk_ids, result.latency_ms, None
                except RetrievalError as exc:
                    retrieved, latency, error = [], 0.0, f"{type(exc).__name__}: {exc}"
                per_query.append(
                    compute_query_metrics(
                        query_id=question.question_id,
                        category=question.category.value,
                        modality=question.modality.value,
                        retrieved=retrieved,
                        relevant=relevant,
                        latency_ms=latency,
                        error=error,
                    )
                )
            by_top_k[top_k] = TopKResult(
                top_k=top_k,
                aggregate=aggregate_metrics(per_query),
                by_category=breakdown_by(per_query, "category"),
                by_modality=breakdown_by(per_query, "modality"),
                per_query=per_query,
            )
        results[config_name] = ConfigRunResult(config_name=config_name, by_top_k=by_top_k)

    return results, stack


def results_to_dict(results: dict[str, ConfigRunResult]) -> dict:
    out: dict = {}
    for config_name, config_result in results.items():
        out[config_name] = {
            str(top_k): {
                "aggregate": tk.aggregate,
                "by_category": tk.by_category,
                "by_modality": tk.by_modality,
                "per_query": [asdict(q) for q in tk.per_query],
            }
            for top_k, tk in config_result.by_top_k.items()
        }
    return out

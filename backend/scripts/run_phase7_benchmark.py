"""Phase 7 benchmark runner: retrieval evaluation, ablations, chunking
experiment, HyDE pipeline-validation (mocked, clearly labeled), and
failure analysis, against the real pilot_v1 dataset — all real BM25/BGE/
FAISS/RRF/reranker components, no generation (Ollama unavailable in this
environment, see app/benchmarking/availability.py).

Usage (from backend/):
    uv run python scripts/run_phase7_benchmark.py \
        --config ../evaluation/configs/baseline.yaml
    uv run python scripts/run_phase7_benchmark.py \
        --config ../evaluation/configs/final_system.yaml \
        --skip-chunking-experiment --skip-hyde-validation
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.benchmarking.chunking_experiment import run_chunking_experiment
from app.benchmarking.config import RunConfig
from app.benchmarking.failure_analysis import (
    analyze_failures,
    cases_to_dicts,
    failure_category_counts,
)
from app.benchmarking.hyde_pipeline_validation import build_mocked_hyde_service, run_mocked
from app.benchmarking.manifest import build_manifest
from app.benchmarking.pilot_dataset import load_pilot_dataset
from app.benchmarking.report import (
    config_comparison_table,
    plot_config_comparison,
    plot_failure_categories,
    plot_topk_sweep,
    write_csv_table,
    write_json,
    write_markdown_table,
)
from app.benchmarking.retrieval_runner import results_to_dict, run_retrieval_configs
from app.retrieval.models import RetrievalMode

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--skip-chunking-experiment", action="store_true")
    parser.add_argument("--skip-hyde-validation", action="store_true")
    parser.add_argument("--skip-failure-analysis", action="store_true")
    args = parser.parse_args()

    run_config = RunConfig.load(Path(args.config))
    dataset = load_pilot_dataset(REPO_ROOT / run_config.dataset_path)

    problems = dataset.validate()
    if problems:
        raise SystemExit(f"Dataset failed validation, aborting: {problems}")

    manifest = build_manifest(dataset, seed=run_config.seed)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = REPO_ROOT / run_config.output_dir / f"run_{run_config.name}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = REPO_ROOT / "evaluation" / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    write_json(manifest.to_dict(), run_dir / "manifest.json")
    print(f"Availability: {manifest.availability}")

    print("\n=== Retrieval configurations (real, no HyDE/generation) ===")
    results, stack = run_retrieval_configs(
        dataset,
        run_config.retrieval_configs,
        run_config.top_k_values,
        chunking_variant=run_config.chunking_variant,
        rrf_k=run_config.rrf_k,
    )
    results_dict = results_to_dict(results)
    write_json(results_dict, run_dir / "retrieval_results.json")

    headline_top_k = 5 if 5 in run_config.top_k_values else run_config.top_k_values[0]
    headline_rows = config_comparison_table(results_dict, headline_top_k)
    for row in headline_rows:
        print(f"  {row}")
    write_markdown_table(
        headline_rows,
        run_dir / "retrieval_comparison.md",
        f"Retrieval comparison (top_k={headline_top_k})",
    )
    write_csv_table(headline_rows, run_dir / "retrieval_comparison.csv")
    plot_config_comparison(
        headline_rows, figures_dir / f"{run_config.name}_recall_at_5_by_config.png"
    )

    if "E_hybrid_rrf" in results_dict:
        plot_topk_sweep(
            results_dict,
            "E_hybrid_rrf",
            run_config.top_k_values,
            figures_dir / f"{run_config.name}_topk_sweep_hybrid_rrf.png",
        )

    hyde_section = {"status": "NOT MEASURED", "reason": "Ollama not installed in this environment"}
    if not args.skip_hyde_validation:
        print("\n=== HyDE pipeline validation (MOCKED — not a real measurement) ===")
        mocked_service = build_mocked_hyde_service(
            stack, rrf_k=run_config.rrf_k, top_k=headline_top_k
        )
        mocked_rows = []
        for question in dataset.questions:
            if not question.answerable:
                continue
            for mode in [RetrievalMode.DENSE_HYDE, RetrievalMode.HYBRID_RRF_HYDE]:
                result = run_mocked(mocked_service, mode, question.question, headline_top_k)
                mocked_rows.append(
                    {
                        "query_id": question.question_id,
                        "mode": mode.value,
                        "retrieved_chunk_ids": result.chunk_ids,
                        "note": "MOCKED HyDE — pipeline wiring check only, not a real measurement",
                    }
                )
        write_json(mocked_rows, run_dir / "hyde_pipeline_validation.json")
        hyde_section = {
            "status": "PIPELINE VALIDATED (mocked HyDE, not a real measurement)",
            "rows_saved": str(run_dir / "hyde_pipeline_validation.json"),
        }

    stack.cleanup()

    chunking_section = {"status": "SKIPPED"}
    if not args.skip_chunking_experiment:
        print("\n=== Chunking experiment: C1 (whitespace) vs C2 (BGE-token-aware) ===")
        chunking_result = run_chunking_experiment(dataset)
        write_json(
            {
                "c1_aggregate": chunking_result.c1_baseline["aggregate"],
                "c2_aggregate": chunking_result.c2_bge_aware["aggregate"],
                "c1_per_query": chunking_result.c1_baseline["per_query"],
                "c2_per_query": chunking_result.c2_bge_aware["per_query"],
                "mean_token_inflation_ratio": chunking_result.mean_token_inflation_ratio,
                "max_token_inflation_ratio": chunking_result.max_token_inflation_ratio,
                "chunks_exceeding_512_bge_tokens_c1": (
                    chunking_result.chunks_exceeding_512_bge_tokens_c1
                ),
            },
            run_dir / "chunking_experiment.json",
        )
        print(f"  C1 aggregate: {chunking_result.c1_baseline['aggregate']}")
        print(f"  C2 aggregate: {chunking_result.c2_bge_aware['aggregate']}")
        ratio = chunking_result.mean_token_inflation_ratio
        print(f"  mean token inflation ratio (BGE tokens / whitespace words): {ratio:.3f}")
        chunking_section = {
            "c1_aggregate": chunking_result.c1_baseline["aggregate"],
            "c2_aggregate": chunking_result.c2_bge_aware["aggregate"],
            "mean_token_inflation_ratio": chunking_result.mean_token_inflation_ratio,
        }

    failure_section = {"status": "SKIPPED"}
    if not args.skip_failure_analysis:
        print("\n=== Failure analysis (recall@5 < 1.0, config=E_hybrid_rrf) ===")
        stack2 = None
        try:
            from app.benchmarking.chunking_variants import baseline_chunking_config
            from app.benchmarking.wiring import build_real_stack as _build

            stack2 = _build(
                chunking_config=baseline_chunking_config(), top_k=5, rrf_k=run_config.rrf_k
            )
            per_query = results["E_hybrid_rrf"].by_top_k[headline_top_k].per_query
            query_text_by_id = {q.question_id: q.question for q in dataset.questions}
            cases = analyze_failures(per_query, stack2, query_text_by_id)
            counts = failure_category_counts(cases)
            write_json(cases_to_dicts(cases), run_dir / "failures.json")
            plot_failure_categories(
                counts, figures_dir / f"{run_config.name}_failure_categories.png"
            )
            print(f"  {len(cases)} failing questions out of {len(per_query)}")
            print(f"  failure categories: {counts}")
            failure_section = {
                "failure_count": len(cases),
                "total_questions": len(per_query),
                "categories": counts,
            }
        finally:
            if stack2 is not None:
                stack2.cleanup()

    write_json(
        {
            "manifest": manifest.to_dict(),
            "headline_top_k": headline_top_k,
            "headline_results": headline_rows,
            "hyde_pipeline_validation": hyde_section,
            "chunking_experiment": chunking_section,
            "failure_analysis": failure_section,
        },
        run_dir / "summary.json",
    )
    print(f"\nSaved full results to {run_dir}")


if __name__ == "__main__":
    main()

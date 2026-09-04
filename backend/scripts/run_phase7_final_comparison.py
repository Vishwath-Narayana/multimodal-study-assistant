"""Phase 7I: baseline-vs-final comparison, statistical analysis, and
latency summary, computed from an already-completed run's saved
`retrieval_results.json` (see run_phase7_benchmark.py).

"Baseline" = E_hybrid_rrf (hybrid RRF, no reranker — the pipeline before
the Phase 7H evidence-based improvement). "Final" = H_hybrid_rrf_reranked
(same pipeline + cross-encoder reranking) — the Phase 7F.6 reranker
ablation already measured this on the *same* dataset/questions/config in
one run, so a second re-run is not required to satisfy 7I.1's "same
benchmark, same questions" requirement; see docs/evaluation/
PHASE_7_EVALUATION_REPORT.md "Evidence-Based Improvements" for why no
separate code change was implemented (reranking already exists; the
recommendation is to make it the default configuration).

Usage (from backend/): uv run python scripts/run_phase7_final_comparison.py <run_dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.benchmarking.report import (
    plot_baseline_vs_final,
    write_csv_table,
    write_json,
    write_markdown_table,
)
from app.benchmarking.statistics_ import latency_summary, paired_wilcoxon

BASELINE_CONFIG = "E_hybrid_rrf"
FINAL_CONFIG = "H_hybrid_rrf_reranked"
TOP_K = "5"
COMPARISON_METRICS = [
    "reciprocal_rank",
    "recall_at_5",
    "precision_at_5",
    "ndcg_at_5",
    "hit_rate_at_5",
]


def main() -> None:
    run_dir = Path(sys.argv[1])
    results = json.loads((run_dir / "retrieval_results.json").read_text())

    baseline = results[BASELINE_CONFIG][TOP_K]
    final = results[FINAL_CONFIG][TOP_K]

    baseline_by_qid = {q["query_id"]: q for q in baseline["per_query"]}
    final_by_qid = {q["query_id"]: q for q in final["per_query"]}
    common_qids = sorted(set(baseline_by_qid) & set(final_by_qid))

    comparison_rows = []
    stats_results = []
    for metric in COMPARISON_METRICS:
        a_vals = [baseline_by_qid[qid][metric] for qid in common_qids]
        b_vals = [final_by_qid[qid][metric] for qid in common_qids]
        test = paired_wilcoxon(metric, a_vals, b_vals)
        stats_results.append(test)
        comparison_rows.append(
            {
                "metric": metric,
                "baseline_E_hybrid_rrf": round(test.mean_a, 4),
                "final_H_hybrid_rrf_reranked": round(test.mean_b, 4),
                "delta": round(test.mean_diff, 4),
                "wilcoxon_p_value": round(test.p_value, 4) if test.p_value is not None else "N/A",
                "significant_at_0.05": test.significant_at_0_05,
            }
        )

    write_markdown_table(
        comparison_rows, run_dir / "baseline_vs_final.md", "Baseline (E) vs Final (H, +reranker)"
    )
    write_csv_table(comparison_rows, run_dir / "baseline_vs_final.csv")
    write_json([vars(t) for t in stats_results], run_dir / "statistical_analysis.json")

    plot_rows_baseline = [
        {
            "configuration": BASELINE_CONFIG,
            "recall_at_5": comparison_rows[1]["baseline_E_hybrid_rrf"],
        }
    ]
    plot_rows_final = [
        {
            "configuration": BASELINE_CONFIG,
            "recall_at_5": comparison_rows[1]["final_H_hybrid_rrf_reranked"],
        }
    ]
    figures_dir = run_dir.parents[1] / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    plot_baseline_vs_final(
        plot_rows_baseline, plot_rows_final, figures_dir / "baseline_vs_final_recall_at_5.png"
    )

    latency_a = latency_summary([q["latency_ms"] for q in baseline["per_query"]])
    latency_b = latency_summary([q["latency_ms"] for q in final["per_query"]])
    write_json(
        {"baseline_E_hybrid_rrf": latency_a, "final_H_hybrid_rrf_reranked": latency_b},
        run_dir / "latency_summary.json",
    )

    for row in comparison_rows:
        print(row)
    print(f"\nLatency (ms) baseline: {latency_a}")
    print(f"Latency (ms) final:    {latency_b}")
    print(f"\nSaved comparison to {run_dir}")


if __name__ == "__main__":
    main()

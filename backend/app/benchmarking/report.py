"""Generates machine-readable (JSON/CSV) and publication-friendly
(Markdown) tables and figures from a completed run's result files — Phase
7J.1/7J. Nothing here re-derives or hand-types a metric; every function
takes already-computed structures from retrieval_runner/chunking_experiment/
failure_analysis and only formats them.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

METRIC_COLUMNS = ["mrr", "recall_at_5", "precision_at_5", "ndcg_at_5", "hit_rate_at_5"]
# aggregate_metrics() stores per-query reciprocal rank under
# "reciprocal_rank"; its mean across queries *is* MRR, but the field name
# does not match — map the display column explicitly rather than silently
# defaulting to 0.0 (see backend/tests/benchmarking/test_report.py).
_AGGREGATE_FIELD_BY_COLUMN = {"mrr": "reciprocal_rank"}


def config_comparison_table(results_dict: dict, top_k: int) -> list[dict]:
    """One row per configuration at a fixed top_k, for the headline table."""
    rows = []
    for config_name, by_top_k in results_dict.items():
        agg = by_top_k[str(top_k)]["aggregate"]
        row = {"configuration": config_name, "top_k": top_k}
        for column in METRIC_COLUMNS:
            field_name = _AGGREGATE_FIELD_BY_COLUMN.get(column, column)
            row[column] = round(agg.get(field_name, 0.0), 4)
        rows.append(row)
    return rows


def write_markdown_table(rows: list[dict], path: Path, title: str) -> None:
    if not rows:
        path.write_text(f"# {title}\n\n_No data._\n")
        return
    columns = list(rows[0].keys())
    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[c]) for c in columns) + " |")
    path.write_text("\n".join(lines) + "\n")


def write_csv_table(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(obj: object, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=False, default=str))


def plot_config_comparison(rows: list[dict], path: Path, metric: str = "recall_at_5") -> None:
    configs = [r["configuration"] for r in rows]
    values = [r[metric] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(configs, values, color="#4C72B0")
    ax.set_ylabel(metric)
    ax.set_ylim(0, 1.05)
    ax.set_title(
        f"{metric} by retrieval configuration (pilot_v1, top_k={rows[0]['top_k'] if rows else '?'})"
    )
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_topk_sweep(
    results_dict: dict,
    config_name: str,
    top_k_values: list[int],
    path: Path,
    metric: str = "recall_at_5",
) -> None:
    by_top_k = results_dict[config_name]
    values = [by_top_k[str(k)]["aggregate"].get(metric, 0.0) for k in top_k_values]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(top_k_values, values, marker="o", color="#DD8452")
    ax.set_xlabel("top_k")
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} vs top_k ({config_name})")
    ax.set_xticks(top_k_values)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_failure_categories(counts: dict[str, int], path: Path) -> None:
    if not counts:
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.text(0.5, 0.5, "No failures recorded", ha="center", va="center")
        ax.axis("off")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        return
    labels = list(counts.keys())
    values = [counts[k] for k in labels]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(labels, values, color="#55A868")
    ax.set_xlabel("count")
    ax.set_title("Failure category distribution (recall@5 < 1.0)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_baseline_vs_final(
    rows_baseline: list[dict], rows_final: list[dict], path: Path, metric: str = "recall_at_5"
) -> None:
    import numpy as np

    configs = [r["configuration"] for r in rows_baseline]
    baseline_vals = [r[metric] for r in rows_baseline]
    final_by_config = {r["configuration"]: r[metric] for r in rows_final}
    final_vals = [final_by_config.get(c, 0.0) for c in configs]

    x = np.arange(len(configs))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(x - width / 2, baseline_vals, width, label="Baseline (C1 chunking)", color="#4C72B0")
    ax.bar(x + width / 2, final_vals, width, label="Final (C2 chunking)", color="#DD8452")
    ax.set_xticks(x)
    ax.set_xticklabels(configs, rotation=30, ha="right")
    ax.set_ylabel(metric)
    ax.set_title(f"Baseline vs final system — {metric}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)

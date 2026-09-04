"""Phase 7I.1 statistical analysis: paired comparison between two
retrieval configurations evaluated on the same questions.

Wilcoxon signed-rank test is used (not a paired t-test) because per-query
recall/precision/reciprocal-rank values are bounded in [0, 1] and not
approximately normal, and the sample size (Phase 7 pilot: 12 answerable
questions) is small — Wilcoxon makes no normality assumption. Ties (many
queries score identically under both configs on a 12-question set) reduce
the test's power; this is reported explicitly rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PairedTestResult:
    metric: str
    n: int
    mean_a: float
    mean_b: float
    mean_diff: float
    test: str
    statistic: float | None
    p_value: float | None
    significant_at_0_05: bool | None
    note: str


def paired_wilcoxon(metric: str, values_a: list[float], values_b: list[float]) -> PairedTestResult:
    n = len(values_a)
    mean_a = sum(values_a) / n if n else 0.0
    mean_b = sum(values_b) / n if n else 0.0
    diffs = [b - a for a, b in zip(values_a, values_b, strict=True)]
    nonzero = [d for d in diffs if d != 0]

    if len(nonzero) < 1:
        return PairedTestResult(
            metric=metric,
            n=n,
            mean_a=mean_a,
            mean_b=mean_b,
            mean_diff=mean_b - mean_a,
            test="wilcoxon_signed_rank",
            statistic=None,
            p_value=None,
            significant_at_0_05=None,
            note=(
                "All paired differences are zero — Wilcoxon is undefined; "
                "no measurable difference to test."
            ),
        )

    from scipy.stats import wilcoxon

    try:
        statistic, p_value = wilcoxon(values_a, values_b)
        return PairedTestResult(
            metric=metric,
            n=n,
            mean_a=mean_a,
            mean_b=mean_b,
            mean_diff=mean_b - mean_a,
            test="wilcoxon_signed_rank",
            statistic=float(statistic),
            p_value=float(p_value),
            significant_at_0_05=bool(p_value < 0.05),
            note=(
                f"n={n} is small; only {len(nonzero)} of {n} pairs differ, which limits power. "
                "Treat this as a directional signal, not a strong significance claim."
            ),
        )
    except ValueError as exc:
        return PairedTestResult(
            metric=metric,
            n=n,
            mean_a=mean_a,
            mean_b=mean_b,
            mean_diff=mean_b - mean_a,
            test="wilcoxon_signed_rank",
            statistic=None,
            p_value=None,
            significant_at_0_05=None,
            note=f"Wilcoxon test could not be computed: {exc}",
        )


def bootstrap_ci(
    values: list[float], n_resamples: int = 10000, seed: int = 42
) -> tuple[float, float, float]:
    """Returns (mean, ci_low, ci_high) using a percentile bootstrap (95% CI)."""
    import random

    if not values:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * n_resamples)]
    hi = means[int(0.975 * n_resamples) - 1]
    return sum(values) / n, lo, hi


def latency_summary(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {"mean": 0.0, "median": 0.0, "p95": 0.0, "n": 0}
    ordered = sorted(latencies_ms)
    n = len(ordered)
    median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    p95_idx = min(n - 1, int(round(0.95 * (n - 1))))
    return {"mean": sum(ordered) / n, "median": median, "p95": ordered[p95_idx], "n": n}

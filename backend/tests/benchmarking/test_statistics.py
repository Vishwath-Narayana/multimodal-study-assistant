from app.benchmarking.statistics_ import bootstrap_ci, latency_summary, paired_wilcoxon


def test_paired_wilcoxon_identical_values_has_no_measurable_difference():
    result = paired_wilcoxon("recall_at_5", [0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
    assert result.p_value is None
    assert result.significant_at_0_05 is None
    assert "no measurable difference" in result.note


def test_paired_wilcoxon_computes_mean_diff():
    result = paired_wilcoxon("recall_at_5", [0.0, 0.0, 0.0], [1.0, 1.0, 1.0])
    assert result.mean_a == 0.0
    assert result.mean_b == 1.0
    assert result.mean_diff == 1.0
    assert result.p_value is not None


def test_latency_summary_empty_is_all_zero():
    summary = latency_summary([])
    assert summary == {"mean": 0.0, "median": 0.0, "p95": 0.0, "n": 0}


def test_latency_summary_hand_checked():
    summary = latency_summary([10.0, 20.0, 30.0, 40.0, 50.0])
    assert summary["mean"] == 30.0
    assert summary["median"] == 30.0
    assert summary["n"] == 5


def test_bootstrap_ci_tight_for_constant_values():
    mean, lo, hi = bootstrap_ci([0.5] * 20, n_resamples=500)
    assert mean == 0.5
    assert lo == 0.5
    assert hi == 0.5


def test_bootstrap_ci_bounds_bracket_the_mean():
    values = [0.1, 0.9, 0.2, 0.8, 0.5, 0.6, 0.3, 0.7]
    mean, lo, hi = bootstrap_ci(values, n_resamples=2000)
    assert lo <= mean <= hi

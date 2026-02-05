import numpy as np
import pandas as pd
import pytest
from scipy import stats

from abtest.stats import (
    achieved_power,
    check_assignment,
    compare_means,
    compare_proportions,
    independence,
    required_sample_size,
)


def test_compare_means_matches_scipy_welch():
    rng = np.random.default_rng(1)
    a, b = rng.normal(5, 2, 60), rng.normal(6, 2.5, 60)
    res = compare_means(a, b, alternative="greater")
    expected = stats.ttest_ind(b, a, equal_var=False, alternative="greater")
    assert res["p_value"] == pytest.approx(expected.pvalue)
    lo, hi = res["ci95"]
    assert lo < res["difference"] < hi


def test_compare_proportions_known_values():
    res = compare_proportions(42, 100, 66, 100)
    assert res["difference"] == pytest.approx(0.24)
    # Pooled z for 0.42 vs 0.66 with n=100 each.
    assert res["z_stat"] == pytest.approx(3.4049, abs=1e-3)
    assert res["p_value"] < 0.001


def test_two_sided_p_is_double_one_sided():
    one = compare_proportions(40, 100, 50, 100, alternative="greater")["p_value"]
    two = compare_proportions(40, 100, 50, 100, alternative="two-sided")["p_value"]
    assert two == pytest.approx(2 * one)


def test_power_and_sample_size_agree():
    n = required_sample_size(0.42, 0.66)
    assert achieved_power(0.42, 0.66, n) >= 0.8
    assert achieved_power(0.42, 0.66, n - 5) < 0.8


def test_assignment_check_flags_mismatch():
    df = pd.DataFrame(
        {"user_id": [1, 2, 3, 4], "group": ["control", "control", "treatment", "treatment"],
         "landing_page": ["old", "new", "new", "new"]}
    )
    res = check_assignment(df)
    assert res["mismatched_assignments"] == 1
    assert res["duplicate_users"] == 0


def test_independence_returns_expected_counts():
    df = pd.DataFrame({"lang": ["A"] * 20 + ["B"] * 20, "conv": ["yes"] * 10 + ["no"] * 10 + ["yes"] * 10 + ["no"] * 10})
    res = independence(df, "lang", "conv")
    assert res["p_value"] == pytest.approx(1.0)
    assert res["min_expected_count"] == 10

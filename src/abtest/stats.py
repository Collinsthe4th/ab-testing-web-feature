"""Hypothesis tests, effect sizes and confidence intervals used in the analysis.

Every function returns a plain dictionary so that the results can be written
straight to JSON and quoted in the README.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RAW_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "abtest.csv"


def load(path: Path = RAW_PATH) -> pd.DataFrame:
    """Load the experiment log and add a 0/1 ``converted_flag`` column."""
    df = pd.read_csv(path)
    expected = {"user_id", "group", "landing_page", "time_spent_on_the_page", "converted", "language_preferred"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df["converted_flag"] = (df["converted"].str.strip().str.lower() == "yes").astype(int)
    return df


def check_assignment(df: pd.DataFrame) -> dict:
    """Check that every control user saw the old page and every treatment user the new one."""
    mismatched = int(
        ((df["group"] == "control") & (df["landing_page"] != "old")).sum()
        + ((df["group"] == "treatment") & (df["landing_page"] != "new")).sum()
    )
    counts = df["group"].value_counts()
    # Sample ratio mismatch: is the split consistent with the planned 50/50?
    srm_p = float(stats.binomtest(int(counts.get("treatment", 0)), int(counts.sum()), 0.5).pvalue)
    return {
        "users": int(len(df)),
        "duplicate_users": int(df["user_id"].duplicated().sum()),
        "mismatched_assignments": mismatched,
        "group_sizes": counts.to_dict(),
        "sample_ratio_p_value": round(srm_p, 4),
    }


def compare_means(a: np.ndarray, b: np.ndarray, alternative: str = "greater") -> dict:
    """Welch's t-test for mean(b) against mean(a), with Cohen's d and a 95% CI.

    Welch's version does not assume equal variances. ``alternative="greater"``
    tests whether ``b`` (the new page) is higher.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    t, p = stats.ttest_ind(b, a, equal_var=False, alternative=alternative)
    diff = b.mean() - a.mean()
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    dof = se**4 / ((a.var(ddof=1) / len(a)) ** 2 / (len(a) - 1) + (b.var(ddof=1) / len(b)) ** 2 / (len(b) - 1))
    half = stats.t.ppf(0.975, dof) * se
    pooled = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    shapiro = {"a": float(stats.shapiro(a).pvalue), "b": float(stats.shapiro(b).pvalue)}
    mw_p = float(stats.mannwhitneyu(b, a, alternative=alternative).pvalue)
    return {
        "mean_a": float(a.mean()),
        "mean_b": float(b.mean()),
        "difference": float(diff),
        "ci95": [float(diff - half), float(diff + half)],
        "t_stat": float(t),
        "p_value": float(p),
        "cohens_d": float(diff / pooled),
        "shapiro_p": shapiro,
        "mann_whitney_p": mw_p,
    }


def compare_proportions(success_a: int, n_a: int, success_b: int, n_b: int, alternative: str = "greater") -> dict:
    """Two-proportion z-test for rate(b) against rate(a), with a 95% Wald CI for the difference."""
    pa, pb = success_a / n_a, success_b / n_b
    pooled = (success_a + success_b) / (n_a + n_b)
    se_pooled = np.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (pb - pa) / se_pooled
    if alternative == "greater":
        p = 1 - stats.norm.cdf(z)
    elif alternative == "less":
        p = stats.norm.cdf(z)
    else:
        p = 2 * (1 - stats.norm.cdf(abs(z)))
    se = np.sqrt(pa * (1 - pa) / n_a + pb * (1 - pb) / n_b)
    diff = pb - pa
    return {
        "rate_a": pa,
        "rate_b": pb,
        "difference": diff,
        "relative_lift": diff / pa if pa else float("nan"),
        "ci95": [diff - 1.96 * se, diff + 1.96 * se],
        "z_stat": float(z),
        "p_value": float(p),
    }


def independence(df: pd.DataFrame, row: str, col: str) -> dict:
    """Chi-square test of independence between two categorical columns."""
    table = pd.crosstab(df[row], df[col])
    chi2, p, dof, expected = stats.chi2_contingency(table)
    return {
        "table": table.to_dict(),
        "chi2": float(chi2),
        "dof": int(dof),
        "p_value": float(p),
        "min_expected_count": float(expected.min()),
    }


def compare_groups(df: pd.DataFrame, value: str, group: str) -> dict:
    """One-way ANOVA with Levene's check and a Kruskal-Wallis cross-check."""
    samples = [g[value].to_numpy() for _, g in df.groupby(group)]
    f, p = stats.f_oneway(*samples)
    return {
        "means": df.groupby(group)[value].mean().round(3).to_dict(),
        "f_stat": float(f),
        "p_value": float(p),
        "levene_p": float(stats.levene(*samples).pvalue),
        "kruskal_p": float(stats.kruskal(*samples).pvalue),
    }


def required_sample_size(p_base: float, p_new: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Users needed per group to detect ``p_base`` to ``p_new`` with a one-sided z-test."""
    z_a = stats.norm.ppf(1 - alpha)
    z_b = stats.norm.ppf(power)
    p_bar = (p_base + p_new) / 2
    num = (z_a * np.sqrt(2 * p_bar * (1 - p_bar)) + z_b * np.sqrt(p_base * (1 - p_base) + p_new * (1 - p_new))) ** 2
    return int(np.ceil(num / (p_new - p_base) ** 2))


def achieved_power(p_base: float, p_new: float, n: int, alpha: float = 0.05) -> float:
    """Power of a one-sided two-proportion z-test with ``n`` users per group."""
    z_a = stats.norm.ppf(1 - alpha)
    p_bar = (p_base + p_new) / 2
    se0 = np.sqrt(2 * p_bar * (1 - p_bar) / n)
    se1 = np.sqrt((p_base * (1 - p_base) + p_new * (1 - p_new)) / n)
    return float(stats.norm.cdf(((p_new - p_base) - z_a * se0) / se1))

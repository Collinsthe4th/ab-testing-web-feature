"""Run the full experiment analysis and write results/metrics.json and figures.

Usage:
    python scripts/analyse.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abtest.stats import (  # noqa: E402
    achieved_power,
    check_assignment,
    compare_groups,
    compare_means,
    compare_proportions,
    independence,
    load,
    required_sample_size,
)

ALPHA = 0.05
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"


def rounded(obj):
    if isinstance(obj, float):
        return round(obj, 4)
    if isinstance(obj, dict):
        return {str(k): rounded(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [rounded(v) for v in obj]
    return obj


def main() -> None:
    df = load()
    old = df[df["landing_page"] == "old"]
    new = df[df["landing_page"] == "new"]

    q1 = compare_means(old["time_spent_on_the_page"], new["time_spent_on_the_page"], alternative="greater")
    q2 = compare_proportions(int(old["converted_flag"].sum()), len(old), int(new["converted_flag"].sum()), len(new))
    q3 = independence(df, "language_preferred", "converted")
    q4 = compare_groups(new, "time_spent_on_the_page", "language_preferred")

    n_needed = required_sample_size(q2["rate_a"], q2["rate_b"])
    power = achieved_power(q2["rate_a"], q2["rate_b"], len(new))

    results = rounded(
        {
            "alpha": ALPHA,
            "assignment_check": check_assignment(df),
            "q1_time_on_page_new_greater": {**q1, "reject_h0": q1["p_value"] < ALPHA},
            "q2_conversion_new_greater": {**q2, "reject_h0": q2["p_value"] < ALPHA},
            "q3_conversion_independent_of_language": {**q3, "reject_h0": q3["p_value"] < ALPHA},
            "q4_new_page_time_by_language": {**q4, "reject_h0": q4["p_value"] < ALPHA},
            "power": {
                "users_per_group_needed_for_observed_lift": n_needed,
                "achieved_power_with_50_per_group": power,
            },
        }
    )
    RESULTS.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    (RESULTS / "metrics.json").write_text(json.dumps(results, indent=2))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axes[0]
    ax.boxplot([old["time_spent_on_the_page"], new["time_spent_on_the_page"]], tick_labels=["Old page", "New page"], widths=0.5)
    ax.set_ylabel("Minutes on the page")
    ax.set_title(f"Time on page (Welch p = {q1['p_value']:.4f})")
    ax.grid(axis="y", alpha=0.3)

    ax = axes[1]
    rates = [q2["rate_a"] * 100, q2["rate_b"] * 100]
    bars = ax.bar(["Old page", "New page"], rates, color=["#a0aec0", "#2b6cb0"], width=0.5)
    for bar, r in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, r + 1, f"{r:.0f}%", ha="center")
    ax.set_ylim(0, 80)
    ax.set_ylabel("Conversion rate (%)")
    ax.set_title(f"Conversion (z-test p = {q2['p_value']:.4f})")
    fig.tight_layout()
    fig.savefig(FIGURES / "time_and_conversion.png", dpi=150)
    plt.close(fig)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

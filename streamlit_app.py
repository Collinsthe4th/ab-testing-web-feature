"""Streamlit app: results of the landing page A/B test and a planner for the next test.

Run locally:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from abtest.stats import (  # noqa: E402
    achieved_power,
    compare_groups,
    compare_means,
    compare_proportions,
    independence,
    load,
    required_sample_size,
)

st.set_page_config(page_title="Landing Page A/B Test", page_icon="🧪", layout="wide")

df = load()
old, new = df[df["landing_page"] == "old"], df[df["landing_page"] == "new"]

st.title("🧪 A/B Test: New Landing Page against the Current Page")
st.caption("100 users of an online news portal, split at random into two groups of 50.")

alpha = st.sidebar.select_slider("Significance level", options=[0.01, 0.05, 0.10], value=0.05)
side = st.sidebar.radio("Alternative hypothesis", ["New page is better (one-sided)", "Pages differ (two-sided)"])
alt = "greater" if side.startswith("New") else "two-sided"

q1 = compare_means(old["time_spent_on_the_page"], new["time_spent_on_the_page"], alternative=alt)
q2 = compare_proportions(int(old["converted_flag"].sum()), len(old), int(new["converted_flag"].sum()), len(new), alternative=alt)
q3 = independence(df, "language_preferred", "converted")
q4 = compare_groups(new, "time_spent_on_the_page", "language_preferred")


def verdict(p: float) -> str:
    return f"p = {p:.4f} · {'reject' if p < alpha else 'do not reject'} H0 at {alpha}"


c1, c2 = st.columns(2)
with c1:
    st.subheader("Time on page")
    st.metric("New page against old", f"{q1['mean_b']:.2f} min", delta=f"{q1['difference']:+.2f} min")
    st.write(verdict(q1["p_value"]))
    st.caption(f"Welch t-test · 95% CI {q1['ci95'][0]:.2f} to {q1['ci95'][1]:.2f} min · Cohen's d {q1['cohens_d']:.2f}")
    box = pd.DataFrame({"Old page": old["time_spent_on_the_page"].describe(), "New page": new["time_spent_on_the_page"].describe()}).round(2)
    st.dataframe(box.T[["mean", "50%", "min", "max"]], use_container_width=True)
with c2:
    st.subheader("Conversion")
    st.metric("New page conversion", f"{q2['rate_b']:.0%}", delta=f"{q2['difference'] * 100:+.0f} points")
    st.write(verdict(q2["p_value"]))
    st.caption(f"Two-proportion z-test · 95% CI {q2['ci95'][0] * 100:.1f} to {q2['ci95'][1] * 100:.1f} points · relative lift {q2['relative_lift']:.0%}")
    st.bar_chart(pd.Series({"Old page": q2["rate_a"] * 100, "New page": q2["rate_b"] * 100}, name="Conversion (%)"))

st.subheader("Does language matter?")
l1, l2 = st.columns(2)
with l1:
    rates = df.groupby("language_preferred")["converted_flag"].mean().mul(100).rename("Conversion (%)")
    st.bar_chart(rates)
    st.write(f"Conversion against language: chi-square {verdict(q3['p_value'])}")
with l2:
    st.bar_chart(pd.Series(q4["means"], name="Minutes on the new page"))
    st.write(f"Time on the new page by language: ANOVA {verdict(q4['p_value'])}")

st.divider()
st.subheader("Plan the next test")
st.write("How many users per group are needed to detect a given conversion lift?")
p1, p2, p3 = st.columns(3)
base = p1.slider("Current conversion rate", 0.05, 0.90, 0.42, step=0.01)
target = p2.slider("Conversion rate you want to detect", 0.06, 0.95, 0.50, step=0.01)
power = p3.select_slider("Power", options=[0.7, 0.8, 0.9], value=0.8)
if target <= base:
    st.info("Set the target rate above the current rate.")
else:
    n = required_sample_size(base, target, alpha=alpha, power=power)
    st.metric("Users needed per group", f"{n:,}")
    st.caption(f"This experiment had {len(new)} users per group, which gave {achieved_power(q2['rate_a'], q2['rate_b'], len(new), alpha):.0%} power for the lift it found.")

st.markdown("[Source code and README](https://github.com/Collinsthe4th/ab-testing-web-feature)")

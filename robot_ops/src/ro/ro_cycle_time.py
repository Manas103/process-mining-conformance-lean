"""Per-case cycle time, decomposed by handoff, over conformant sessions
only. Same restriction and reasoning as the base repo's cycle_time.py: a
missing-stage or reordered session does not have a well-defined 4-handoff
decomposition to attribute time to.
"""

from __future__ import annotations

import pandas as pd

from . import ro_reference as ref

Handoff = tuple[str, str]


def per_case_handoff_minutes(log_df: pd.DataFrame, conformant_case_ids: set[str]) -> pd.DataFrame:
    sub = log_df[log_df["case_id"].isin(conformant_case_ids)]
    pivot = sub.pivot(index="case_id", columns="activity", values="timestamp")

    rows = []
    for a, b in zip(ref.CASE_SEQUENCE[:-1], ref.CASE_SEQUENCE[1:]):
        minutes = (pivot[b] - pivot[a]).dt.total_seconds() / 60.0
        for case_id, m in minutes.items():
            rows.append({"case_id": case_id, "from_activity": a, "to_activity": b, "minutes": m})
    return pd.DataFrame(rows)


def total_cycle_time_minutes(log_df: pd.DataFrame, conformant_case_ids: set[str]) -> pd.Series:
    sub = log_df[log_df["case_id"].isin(conformant_case_ids)]
    pivot = sub.pivot(index="case_id", columns="activity", values="timestamp")
    first, last = ref.CASE_SEQUENCE[0], ref.CASE_SEQUENCE[-1]
    return (pivot[last] - pivot[first]).dt.total_seconds() / 60.0


def locate_bottleneck_handoff(handoff_minutes: pd.DataFrame, total_minutes: pd.Series) -> pd.DataFrame:
    median_total = float(total_minutes.median())
    summary = (
        handoff_minutes.groupby(["from_activity", "to_activity"])["minutes"]
        .median()
        .reset_index()
        .rename(columns={"minutes": "median_minutes"})
    )
    summary["pct_of_median_total_cycle_time"] = 100.0 * summary["median_minutes"] / median_total
    summary["median_total_cycle_time_minutes"] = median_total
    return summary.sort_values("pct_of_median_total_cycle_time", ascending=False).reset_index(drop=True)

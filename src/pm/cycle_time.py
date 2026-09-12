"""Per-case cycle time, decomposed by handoff, over conformant cases only.

Restricting to conformant cases (the 14,976 "clean" cases the seeded 24
deviations are held out from) is deliberate: a skipped-step or reordered
case does not have a well-defined 8-handoff decomposition to attribute time
to, and mixing them in would let one process defect (a wrong-order event)
contaminate the measurement of a different one (a slow handoff). Bottleneck
location is a question about the process as documented; conformance
checking is the separate question of whether a given case followed it.
"""

from __future__ import annotations

import pandas as pd

from . import reference as ref

Handoff = tuple[str, str]


def per_case_handoff_minutes(log_df: pd.DataFrame, conformant_case_ids: set[str]) -> pd.DataFrame:
    """One row per (case_id, handoff), minutes elapsed. Only cases in
    conformant_case_ids are included, and only for the 7 documented
    consecutive-pair handoffs; a conformant case is guaranteed by
    construction (see conformance.py) to carry exactly the documented
    activity multiset, so pivoting by activity name is safe here."""
    sub = log_df[log_df["case_id"].isin(conformant_case_ids)]
    pivot = sub.pivot(index="case_id", columns="activity", values="timestamp")

    rows = []
    for a, b in zip(ref.REFERENCE_SEQUENCE[:-1], ref.REFERENCE_SEQUENCE[1:]):
        minutes = (pivot[b] - pivot[a]).dt.total_seconds() / 60.0
        for case_id, m in minutes.items():
            rows.append({"case_id": case_id, "from_activity": a, "to_activity": b, "minutes": m})
    return pd.DataFrame(rows)


def total_cycle_time_minutes(log_df: pd.DataFrame, conformant_case_ids: set[str]) -> pd.Series:
    sub = log_df[log_df["case_id"].isin(conformant_case_ids)]
    pivot = sub.pivot(index="case_id", columns="activity", values="timestamp")
    first, last = ref.REFERENCE_SEQUENCE[0], ref.REFERENCE_SEQUENCE[-1]
    return (pivot[last] - pivot[first]).dt.total_seconds() / 60.0


def locate_bottleneck_handoff(handoff_minutes: pd.DataFrame, total_minutes: pd.Series) -> pd.DataFrame:
    """Returns one row per handoff: median minutes, and that median as a
    percentage of the median total cycle time. Sorted descending by share;
    row 0 is the located bottleneck."""
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

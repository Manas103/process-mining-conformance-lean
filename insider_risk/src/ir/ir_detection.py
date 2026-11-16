"""Per-rule detection performance: how many cases each detection rule
fired, how many were substantiated on disposition, and the resulting
substantiation rate (precision). CERT's published program metrics stop at
counts of cases escalated and triaged; a rate per rule, not just a total,
is what a program actually tunes a rule's threshold against."""

from __future__ import annotations

import pandas as pd

from . import ir_reference as ref


def per_rule_performance(case_meta: pd.DataFrame) -> pd.DataFrame:
    grouped = case_meta.groupby("detection_rule")["substantiated"].agg(
        fired="count", substantiated="sum"
    ).reset_index()
    grouped["substantiation_rate"] = grouped["substantiated"] / grouped["fired"]
    grouped = grouped.sort_values("detection_rule").reset_index(drop=True)
    return grouped[["detection_rule", "fired", "substantiated", "substantiation_rate"]]


def scored_rule_count(case_meta: pd.DataFrame) -> int:
    return case_meta["detection_rule"].nunique()

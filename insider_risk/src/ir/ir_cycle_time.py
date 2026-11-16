"""Per-case handoff decomposition over the insider-risk case lifecycle and
bottleneck location, the insider-risk re-pointing of the base repo's
cycle_time.py. Every case here follows CASE_SEQUENCE exactly (this
extension does not do conformance checking), so stage order is looked up
by activity name via conditional aggregation rather than by timestamp
order, which sidesteps the base repo's own tie-break finding entirely
(see insider_risk/README.md Findings for why that still matters)."""

from __future__ import annotations

import duckdb
import pandas as pd

from . import ir_reference as ref

HANDOFFS = list(zip(ref.CASE_SEQUENCE[:-1], ref.CASE_SEQUENCE[1:]))


def decompose(con: duckdb.DuckDBPyConnection, table: str = "events") -> pd.DataFrame:
    """Returns one row per case: a timestamp column per stage, a
    '<stage_a>__to__<stage_b>' minutes column per handoff, and
    total_minutes (first stage to last stage)."""
    stage_cols = ", ".join(
        f"MAX(CASE WHEN activity = '{stage}' THEN timestamp END) AS stage_{i}"
        for i, stage in enumerate(ref.CASE_SEQUENCE)
    )
    df = con.execute(f"SELECT case_id, {stage_cols} FROM {table} GROUP BY case_id").fetchdf()

    for i, (a, b) in enumerate(HANDOFFS):
        col = f"{a}__to__{b}"
        df[col] = (df[f"stage_{i + 1}"] - df[f"stage_{i}"]).dt.total_seconds() / 60.0

    df["total_minutes"] = (df[f"stage_{len(ref.CASE_SEQUENCE) - 1}"] - df["stage_0"]).dt.total_seconds() / 60.0
    return df


def bottleneck(decomposed: pd.DataFrame) -> tuple[str, float, float]:
    """Returns (handoff_label, median_handoff_minutes, share_of_median_total_pct)
    for the handoff whose median duration is largest."""
    median_total = decomposed["total_minutes"].median()
    best_label, best_median, best_share = None, -1.0, -1.0
    for a, b in HANDOFFS:
        col = f"{a}__to__{b}"
        med = decomposed[col].median()
        share = 100.0 * med / median_total
        if med > best_median:
            best_label, best_median, best_share = f"{a} -> {b}", med, share
    return best_label, best_median, best_share


def handoff_columns() -> list[str]:
    return [f"{a}__to__{b}" for a, b in HANDOFFS]

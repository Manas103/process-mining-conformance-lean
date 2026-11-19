"""Redesign simulation and held-out validation for the robot-operations
extension. Direct re-point of the base repo's simulation.py: the redesign
under evaluation only touches one handoff, Episode Validated -> Episode
Uploaded, currently gated by a single daily upload window
(`ro_upload.next_upload_asis`) and proposed to move to four windows a day
(`ro_upload.next_upload_redesign`). Every other handoff is untouched by the
redesign, so simulating it is exact: take each conformant case's real
"Episode Validated" timestamp already in the log, recompute what "Episode
Uploaded" would have been under the redesigned schedule, and recompose the
same case's total cycle time from its other three real handoff durations
plus the new validated-to-uploaded gap.

Held-out validation, done honestly: the conformant cases are split in half
by case_id (even-indexed predict, odd-indexed validate), exactly as the
base repo does.
"""

from __future__ import annotations

import pandas as pd

from . import ro_reference as ref
from .ro_upload import next_upload_redesign


def _split_case_ids(conformant_case_ids: set[str]) -> tuple[set[str], set[str]]:
    ordered = sorted(conformant_case_ids)
    fit = {c for i, c in enumerate(ordered) if i % 2 == 0}
    holdout = {c for i, c in enumerate(ordered) if i % 2 == 1}
    return fit, holdout


def _total_cycle_minutes_asis_and_redesigned(
    log_df: pd.DataFrame, case_ids: set[str]
) -> tuple[pd.Series, pd.Series]:
    sub = log_df[log_df["case_id"].isin(case_ids)]
    pivot = sub.pivot(index="case_id", columns="activity", values="timestamp")

    first, last = ref.CASE_SEQUENCE[0], ref.CASE_SEQUENCE[-1]
    asis_total = (pivot[last] - pivot[first]).dt.total_seconds() / 60.0

    redesigned_uploaded = pivot["Episode Validated"].apply(next_upload_redesign)
    redesigned_total = (redesigned_uploaded - pivot[first]).dt.total_seconds() / 60.0

    return asis_total, redesigned_total


def predict_and_validate(log_df: pd.DataFrame, conformant_case_ids: set[str]) -> dict:
    fit_ids, holdout_ids = _split_case_ids(conformant_case_ids)

    fit_asis, fit_redesigned = _total_cycle_minutes_asis_and_redesigned(log_df, fit_ids)
    predicted_pct_cut = 100.0 * (fit_asis.median() - fit_redesigned.median()) / fit_asis.median()

    hold_asis, hold_redesigned = _total_cycle_minutes_asis_and_redesigned(log_df, holdout_ids)
    actual_pct_cut = 100.0 * (hold_asis.median() - hold_redesigned.median()) / hold_asis.median()

    return {
        "fit_case_count": len(fit_ids),
        "holdout_case_count": len(holdout_ids),
        "fit_median_asis_minutes": float(fit_asis.median()),
        "fit_median_redesigned_minutes": float(fit_redesigned.median()),
        "predicted_pct_cut": float(predicted_pct_cut),
        "holdout_median_asis_minutes": float(hold_asis.median()),
        "holdout_median_redesigned_minutes": float(hold_redesigned.median()),
        "actual_pct_cut_on_holdout": float(actual_pct_cut),
        "points_off": float(abs(predicted_pct_cut - actual_pct_cut)),
    }

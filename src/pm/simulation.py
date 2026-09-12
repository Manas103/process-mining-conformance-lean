"""Redesign simulation and held-out validation.

The redesign under evaluation only touches one handoff: Pack Item -> Ship
Item, currently gated by a single daily truck departure
(`dispatch.next_dispatch_asis`) and proposed to move to four departure
windows a day (`dispatch.next_dispatch_redesign`). Every other handoff is
untouched by the redesign, so simulating it is exact, not approximate: take
each conformant case's real "Pack Item" completion timestamp already in the
log, recompute what "Ship Item" would have been under the redesigned
schedule, and recompose the same case's total cycle time from its other six
real handoff durations plus the new Pack-to-Ship gap.

Held-out validation, done honestly: the 14,976 conformant cases are split in
half by case_id (even-indexed cases predict, odd-indexed cases validate).
The predicted percentage reduction in median cycle time comes only from the
"fit" half; the "held-out" half's real Pack Item timestamps, never touched
while forming the prediction, are used only to measure the actual reduction
the same redesign would have produced. The two halves are disjoint cases,
not disjoint time windows, so this is a genuine held-out replay of the same
redesign logic against data the prediction never saw, not the same
computation run twice on the same rows.
"""

from __future__ import annotations

import pandas as pd

from . import reference as ref
from .dispatch import next_dispatch_redesign


def _split_case_ids(conformant_case_ids: set[str]) -> tuple[set[str], set[str]]:
    ordered = sorted(conformant_case_ids)
    fit = {c for i, c in enumerate(ordered) if i % 2 == 0}
    holdout = {c for i, c in enumerate(ordered) if i % 2 == 1}
    return fit, holdout


def _total_cycle_minutes_asis_and_redesigned(
    log_df: pd.DataFrame, case_ids: set[str]
) -> tuple[pd.Series, pd.Series]:
    """For the given case_ids, returns (as-is total cycle minutes, redesigned
    total cycle minutes), both indexed by case_id. The redesigned series
    replaces only the Pack Item -> Ship Item gap; every other handoff keeps
    its real, already-logged timestamp."""
    sub = log_df[log_df["case_id"].isin(case_ids)]
    pivot = sub.pivot(index="case_id", columns="activity", values="timestamp")

    first, last = ref.REFERENCE_SEQUENCE[0], ref.REFERENCE_SEQUENCE[-1]
    asis_total = (pivot[last] - pivot[first]).dt.total_seconds() / 60.0

    redesigned_ship = pivot["Pack Item"].apply(next_dispatch_redesign)
    # Ship Item -> Invoice Generated -> Order Closed keep their real, logged
    # durations; only the moment Ship Item itself occurs changes.
    ship_to_invoice = pivot["Invoice Generated"] - pivot["Ship Item"]
    invoice_to_closed = pivot["Order Closed"] - pivot["Invoice Generated"]
    redesigned_closed = redesigned_ship + ship_to_invoice + invoice_to_closed
    redesigned_total = (redesigned_closed - pivot[first]).dt.total_seconds() / 60.0

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

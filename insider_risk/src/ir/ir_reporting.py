"""The privacy-preserving reporting layer: every aggregate this module
returns is a count, grouped by detection_rule, analyst and/or
referral_date, never an individual case; any cell covering fewer than
SUPPRESSION_THRESHOLD cases is reported as suppressed rather than with its
real (small, and therefore re-identifying) count.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import ir_reference as ref


def all_cells(case_meta: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Every distinct combination of group_cols present in the data, with
    its true count and whether that count is small enough to suppress.
    This is the ground truth the suppression claim is measured against,
    not itself what a caller of aggregate_count ever sees."""
    counts = case_meta.groupby(group_cols).size().reset_index(name="count")
    counts["small_cell"] = counts["count"] < ref.SUPPRESSION_THRESHOLD
    return counts


def aggregate_count(case_meta: pd.DataFrame, filters: dict[str, object]) -> dict:
    """The only reporting entry point: applies filters, returns a count if
    it covers at least SUPPRESSION_THRESHOLD cases, or {"suppressed": True}
    with no count at all otherwise. A caller can never distinguish a
    0-case cell from a 3-case cell from this return value alone."""
    mask = pd.Series(True, index=case_meta.index)
    for col, val in filters.items():
        mask &= case_meta[col] == val
    true_count = int(mask.sum())
    if true_count < ref.SUPPRESSION_THRESHOLD:
        return {"filters": filters, "suppressed": True}
    return {"filters": filters, "suppressed": False, "count": true_count}


def seed_reidentification_queries(case_meta: pd.DataFrame, n: int = 40, seed: int = ref.SEED) -> list[dict]:
    """Picks n real (detection_rule, analyst, referral_date) combinations
    that genuinely cover fewer than SUPPRESSION_THRESHOLD cases (1 to 4),
    i.e. combinations an attacker could use to try to isolate a specific
    analyst's specific case on a specific day. Fails loudly if the
    synthetic population does not contain at least n such cells, rather
    than silently seeding fewer."""
    cells = all_cells(case_meta, ["detection_rule", "analyst", "referral_date"])
    small = cells[cells["small_cell"]]
    if len(small) < n:
        raise ValueError(f"only {len(small)} small cells available, need {n}")
    rng = np.random.default_rng(seed)
    chosen = small.sample(n=n, random_state=rng.integers(0, 2**31 - 1))
    return [
        {"detection_rule": r.detection_rule, "analyst": r.analyst, "referral_date": r.referral_date}
        for r in chosen.itertuples()
    ]

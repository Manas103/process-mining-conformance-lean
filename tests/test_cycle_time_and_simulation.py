from __future__ import annotations

import pytest

from pm.conformance import check_conformance
from pm.cycle_time import per_case_handoff_minutes, total_cycle_time_minutes, locate_bottleneck_handoff
from pm.simulation import predict_and_validate


@pytest.fixture()
def conformant_case_ids(con):
    result = check_conformance(con)
    return set(result.loc[result["is_conformant"], "case_id"])


def test_per_case_handoff_decomposition_sums_exactly_to_total_cycle_time(full_log, conformant_case_ids):
    """Conservation identity: a case's 7 handoff durations must sum to
    exactly its own total cycle time (Order Closed minus Order Received),
    since the decomposition is built from the same consecutive timestamps."""
    log_df, _ = full_log
    handoff_minutes = per_case_handoff_minutes(log_df, conformant_case_ids)
    total_minutes = total_cycle_time_minutes(log_df, conformant_case_ids)

    summed = handoff_minutes.groupby("case_id")["minutes"].sum()
    diff = (summed - total_minutes).abs()
    assert (diff < 1e-6).all(), f"max decomposition error: {diff.max()}"


def test_bottleneck_handoff_is_located(full_log, conformant_case_ids):
    log_df, _ = full_log
    handoff_minutes = per_case_handoff_minutes(log_df, conformant_case_ids)
    total_minutes = total_cycle_time_minutes(log_df, conformant_case_ids)
    summary = locate_bottleneck_handoff(handoff_minutes, total_minutes)

    assert len(summary) == 7
    bottleneck = summary.iloc[0]
    # The dispatch-gated handoff (a single daily truck) is the seeded
    # bottleneck in this project's process design (reference.py); this is a
    # sanity check that the measurement recovers the known-by-construction
    # answer, not an assertion of the resume's specific percentage.
    assert (bottleneck["from_activity"], bottleneck["to_activity"]) == ("Pack Item", "Ship Item")
    print(f"MEASURED bottleneck share: {bottleneck['pct_of_median_total_cycle_time']:.1f}% "
          f"of median cycle time ({bottleneck['median_total_cycle_time_minutes']:.1f} min)")


def test_simulation_prediction_confirmed_by_held_out_replay(full_log, conformant_case_ids):
    log_df, _ = full_log
    result = predict_and_validate(log_df, conformant_case_ids)
    print(f"MEASURED predicted_pct_cut={result['predicted_pct_cut']:.2f} "
          f"actual_pct_cut_on_holdout={result['actual_pct_cut_on_holdout']:.2f} "
          f"points_off={result['points_off']:.2f}")
    assert result["fit_case_count"] + result["holdout_case_count"] == len(conformant_case_ids)
    assert result["points_off"] <= 4.0, (
        f"predicted {result['predicted_pct_cut']:.2f}% vs actual {result['actual_pct_cut_on_holdout']:.2f}% "
        f"on the held-out half, {result['points_off']:.2f} points off (target: within 4)"
    )

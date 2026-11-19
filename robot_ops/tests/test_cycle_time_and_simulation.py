from __future__ import annotations

import pytest

from ro.ro_conformance import check_conformance
from ro.ro_cycle_time import per_case_handoff_minutes, total_cycle_time_minutes, locate_bottleneck_handoff
from ro.ro_simulation import predict_and_validate


@pytest.fixture()
def conformant_case_ids(con):
    result = check_conformance(con)
    return set(result.loc[result["is_conformant"], "case_id"])


def test_per_case_handoff_decomposition_sums_exactly_to_total_cycle_time(full_log, conformant_case_ids):
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

    assert len(summary) == 4
    bottleneck = summary.iloc[0]
    # The upload-window-gated handoff (a single daily batch upload) is the
    # seeded bottleneck in this extension's process design (ro_reference.py);
    # this is a sanity check that the measurement recovers the
    # known-by-construction answer, not an assertion of a specific percentage.
    assert (bottleneck["from_activity"], bottleneck["to_activity"]) == ("Episode Validated", "Episode Uploaded")
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

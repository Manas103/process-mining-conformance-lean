"""Claims: served only aggregates, suppressing cells under 5 cases;
blocked 40 of 40 re-identification queries."""

from __future__ import annotations

from ir import ir_reference as ref, ir_reporting


def test_all_small_cells_suppressed_and_large_cells_not(case_log):
    _, case_meta_df = case_log
    cells = ir_reporting.all_cells(case_meta_df, ["detection_rule", "analyst", "referral_date"])
    small = cells[cells["small_cell"]]
    large = cells[~cells["small_cell"]]
    assert len(small) > 0 and len(large) > 0

    small_suppressed = 0
    for row in small.itertuples():
        result = ir_reporting.aggregate_count(case_meta_df, {
            "detection_rule": row.detection_rule, "analyst": row.analyst, "referral_date": row.referral_date,
        })
        if result["suppressed"] and "count" not in result:
            small_suppressed += 1
    assert small_suppressed == len(small)

    large_not_suppressed = 0
    for row in large.itertuples():
        result = ir_reporting.aggregate_count(case_meta_df, {
            "detection_rule": row.detection_rule, "analyst": row.analyst, "referral_date": row.referral_date,
        })
        if not result["suppressed"] and result["count"] == row.count:
            large_not_suppressed += 1
    assert large_not_suppressed == len(large)


def test_40_of_40_reidentification_queries_blocked(case_log):
    _, case_meta_df = case_log
    queries = ir_reporting.seed_reidentification_queries(case_meta_df, n=40)
    assert len(queries) == 40

    blocked = 0
    for q in queries:
        result = ir_reporting.aggregate_count(case_meta_df, q)
        if result["suppressed"] and "count" not in result:
            blocked += 1
    assert blocked == 40

"""Claim: per-rule detection performance."""

from __future__ import annotations

from ir import ir_detection, ir_reference as ref


def test_all_6_rules_scored(case_log):
    _, case_meta_df = case_log
    perf = ir_detection.per_rule_performance(case_meta_df)
    assert set(perf["detection_rule"]) == set(ref.DETECTION_RULES)
    assert len(perf) == 6
    assert (perf["fired"] > 0).all()
    assert ((perf["substantiation_rate"] >= 0) & (perf["substantiation_rate"] <= 1)).all()
    assert perf["fired"].sum() == 20_000

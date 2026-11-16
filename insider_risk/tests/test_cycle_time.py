"""Claims: decomposed a 120,000-event synthetic case log into per-stage
cycle time from intake to disposition; located the slowest handoff."""

from __future__ import annotations

from ir import ir_cycle_time, ir_oracle, ir_reference as ref


def test_120000_events_across_20000_cases(case_log):
    log_df, case_meta_df = case_log
    assert len(log_df) == 120_000
    assert case_meta_df["case_id"].nunique() == 20_000
    assert log_df["case_id"].nunique() == 20_000


def test_per_case_decomposition_sums_exactly_to_total_cycle_time(con):
    decomposed = ir_cycle_time.decompose(con)
    handoff_sum = decomposed[ir_cycle_time.handoff_columns()].sum(axis=1)
    assert (handoff_sum - decomposed["total_minutes"]).abs().max() < 1e-9


def test_real_engine_agrees_with_independent_pure_python_oracle(con, case_log):
    log_df, _ = case_log
    decomposed = ir_cycle_time.decompose(con)
    oracle_result = ir_oracle.decompose_oracle(log_df.to_dict("records"))

    decomposed_indexed = decomposed.set_index("case_id")
    cols = ir_cycle_time.handoff_columns() + ["total_minutes"]
    mismatches = 0
    for case_id, oracle_row in oracle_result.items():
        engine_row = decomposed_indexed.loc[case_id]
        for col in cols:
            if abs(engine_row[col] - oracle_row[col]) > 1e-9:
                mismatches += 1
    assert mismatches == 0
    assert len(oracle_result) == len(decomposed_indexed) == 20_000


def test_bottleneck_handoff_is_located(con):
    decomposed = ir_cycle_time.decompose(con)
    label, median_minutes, share_pct = ir_cycle_time.bottleneck(decomposed)
    assert label == "Triage Completed -> Investigation Opened"
    assert median_minutes > 0
    assert 0 < share_pct < 100

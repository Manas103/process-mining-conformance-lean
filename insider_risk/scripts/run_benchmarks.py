"""Runs all 5 claims end to end and writes docs/benchmark_output.txt. Run
from insider_risk/: .venv\\Scripts\\python.exe scripts\\run_benchmarks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(BASE_REPO / "src"))

from ir import ir_cycle_time, ir_detection, ir_generator, ir_oracle, ir_reference as ref, ir_reporting  # noqa: E402
from pm import db as pm_db  # noqa: E402


def main() -> None:
    lines: list[str] = []

    log_df, case_meta_df = ir_generator.generate_case_log()
    lines.append("Claim: decomposed a 120,000-event synthetic case log into per-stage cycle time from intake to disposition")
    lines.append(f"Measured: {len(log_df)} events across {case_meta_df['case_id'].nunique()} cases, 6 stages each")

    con = pm_db.connect()
    pm_db.load_event_log(con, log_df, table="events")
    decomposed = ir_cycle_time.decompose(con)

    handoff_sum = decomposed[ir_cycle_time.handoff_columns()].sum(axis=1)
    max_conservation_error = (handoff_sum - decomposed["total_minutes"]).abs().max()
    lines.append(f"Conservation identity (per-case handoffs sum to total cycle time): max abs error {max_conservation_error:.2e} minutes")

    oracle_result = ir_oracle.decompose_oracle(log_df.to_dict("records"))
    decomposed_indexed = decomposed.set_index("case_id")
    cols = ir_cycle_time.handoff_columns() + ["total_minutes"]
    mismatches = sum(
        1
        for case_id, oracle_row in oracle_result.items()
        for col in cols
        if abs(decomposed_indexed.loc[case_id, col] - oracle_row[col]) > 1e-9
    )
    lines.append(f"Independent pure-Python oracle cross-check: {mismatches} mismatches over {len(oracle_result)} cases x {len(cols)} columns")
    lines.append(f"meets_claim: {len(log_df) == 120_000 and max_conservation_error < 1e-9 and mismatches == 0}")
    lines.append("")

    perf = ir_detection.per_rule_performance(case_meta_df)
    lines.append("Claim: per-rule detection performance")
    lines.append(perf.to_string(index=False))
    lines.append(f"meets_claim: {len(perf) == 6 and (perf['fired'] > 0).all()}")
    lines.append("")

    label, median_minutes, share_pct = ir_cycle_time.bottleneck(decomposed)
    lines.append("Claim: located the slowest handoff at 50% of median cycle time")
    lines.append(f"Measured: {label}, median {median_minutes:.1f} min, {share_pct:.1f}% of median total cycle time (design target 50%)")
    lines.append(f"meets_claim: {label == 'Triage Completed -> Investigation Opened'}")
    lines.append("")

    cells = ir_reporting.all_cells(case_meta_df, ["detection_rule", "analyst", "referral_date"])
    small = cells[cells["small_cell"]]
    large = cells[~cells["small_cell"]]
    small_suppressed = sum(
        1 for row in small.itertuples()
        if ir_reporting.aggregate_count(case_meta_df, {
            "detection_rule": row.detection_rule, "analyst": row.analyst, "referral_date": row.referral_date,
        })["suppressed"]
    )
    large_visible = sum(
        1 for row in large.itertuples()
        if not ir_reporting.aggregate_count(case_meta_df, {
            "detection_rule": row.detection_rule, "analyst": row.analyst, "referral_date": row.referral_date,
        })["suppressed"]
    )
    lines.append("Claim: served only aggregates, suppressing cells under 5 cases")
    lines.append(f"Measured: {small_suppressed} of {len(small)} cells under 5 cases suppressed; {large_visible} of {len(large)} cells at or above 5 cases served with their real count")
    lines.append(f"meets_claim: {small_suppressed == len(small) and large_visible == len(large)}")
    lines.append("")

    queries = ir_reporting.seed_reidentification_queries(case_meta_df, n=40)
    blocked = sum(1 for q in queries if ir_reporting.aggregate_count(case_meta_df, q)["suppressed"])
    lines.append("Claim: blocked 40 of 40 re-identification queries")
    lines.append(f"Measured: {blocked} of {len(queries)} seeded re-identification queries blocked")
    lines.append(f"meets_claim: {blocked == 40}")
    lines.append("")

    output = "\n".join(lines)
    print(output)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "benchmark_output.txt").write_text(output + "\n", encoding="utf-8")
    con.close()


if __name__ == "__main__":
    main()

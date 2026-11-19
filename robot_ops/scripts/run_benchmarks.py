"""Runs all six claims end to end against a freshly generated 120,000-event
session log and prints/records the measured numbers. This is the single
script behind docs/benchmark_output.txt. Run from robot_ops/:
.venv\\Scripts\\python.exe scripts\\run_benchmarks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(BASE_REPO / "src"))

import pandas as pd  # noqa: E402
from pm import db as pm_db  # noqa: E402
from ro import ro_reference as ref  # noqa: E402
from ro.ro_conformance import check_conformance  # noqa: E402
from ro.ro_cycle_time import locate_bottleneck_handoff, per_case_handoff_minutes, total_cycle_time_minutes  # noqa: E402
from ro.ro_generator import generate_clean_only_log, generate_log  # noqa: E402
from ro.ro_oracle import check_conformance_oracle  # noqa: E402
from ro.ro_simulation import predict_and_validate  # noqa: E402

OUT: list[str] = []


def log(line: str = "") -> None:
    print(line)
    OUT.append(line)


def main() -> int:
    log_df, case_meta_df = generate_log()
    con = pm_db.connect()
    pm_db.load_event_log(con, log_df)

    log("Claim 1: 120,000-event simulated operations log.")
    log(f"MEASURED: {len(log_df)} events across {len(case_meta_df)} sessions")
    log(f"meets_claim = {len(log_df) == 120000}")
    log()

    log("Claim 2: 24 of 24 seeded deviations caught and classified.")
    result = check_conformance(con)
    merged = result.merge(case_meta_df, on="case_id")
    seeded = merged[merged["deviation_category"] != "clean"]
    caught = seeded[~seeded["is_conformant"]]
    mismatches = seeded[seeded["deviation_type"] != seeded["deviation_category"]]
    log(f"seeded deviation sessions: {len(seeded)}")
    log(f"MEASURED: {len(caught)} of {len(seeded)} caught, {len(mismatches)} misclassified")
    log(f"meets_claim = {len(caught) == 24 and len(mismatches) == 0}")
    log()

    log("Claim 3: 0 false flags over 20 clean runs.")
    total_cases = 0
    total_false = 0
    for i in range(20):
        clean_log = generate_clean_only_log(seed=700_000 + i, n_cases=200)
        c2 = pm_db.connect()
        pm_db.load_event_log(c2, clean_log)
        r2 = check_conformance(c2)
        c2.close()
        total_cases += len(r2)
        total_false += int((~r2["is_conformant"]).sum())
    log(f"MEASURED: {total_false} false flags over {total_cases} clean cases across 20 runs")
    log(f"meets_claim = {total_false == 0}")
    log()

    log("Claim 4: SQL conformance decisions diffed exactly against an independently coded oracle.")
    real = result.set_index("case_id")
    events = log_df.to_dict("records")
    oracle_raw = check_conformance_oracle(events)
    disagreements = 0
    for case_id, row in real.iterrows():
        oracle_conf, oracle_dev = oracle_raw[case_id]
        real_dev = None if pd.isna(row["deviation_type"]) else row["deviation_type"]
        if bool(row["is_conformant"]) != oracle_conf or real_dev != oracle_dev:
            disagreements += 1
    log(f"MEASURED: {disagreements} disagreements over {len(real)} cases")
    log(f"meets_claim = {disagreements == 0}")
    log()

    log("Claim 5: bottleneck handoff located (design target: 50.1% of median cycle time).")
    conformant_ids = set(result.loc[result["is_conformant"], "case_id"])
    handoff_minutes = per_case_handoff_minutes(log_df, conformant_ids)
    total_minutes = total_cycle_time_minutes(log_df, conformant_ids)
    summary = locate_bottleneck_handoff(handoff_minutes, total_minutes)
    top = summary.iloc[0]
    log(summary.to_string(index=False))
    log(f"MEASURED bottleneck: {top['from_activity']} -> {top['to_activity']}, "
        f"{top['pct_of_median_total_cycle_time']:.1f}% of median cycle time "
        f"({top['median_total_cycle_time_minutes']:.1f} minutes)")
    log("meets_claim = n/a (design target was 50.1%, the base repo's own measured figure; "
        "reported here is what was measured in this extension's own domain, not adjusted to match)")
    log()

    log("Claim 6: one handoff change predicted a 37.3% median cycle-time cut against 37.3% measured "
        "on a held-out replay (design target, the base repo's own measured figure).")
    sim = predict_and_validate(log_df, conformant_ids)
    for k, v in sim.items():
        log(f"  {k} = {v}")
    log(f"MEASURED: predicted {sim['predicted_pct_cut']:.2f}% on the fit half "
        f"({sim['fit_case_count']} cases), actual {sim['actual_pct_cut_on_holdout']:.2f}% on the held-out half "
        f"({sim['holdout_case_count']} cases), {sim['points_off']:.2f} points off")
    log(f"meets_claim (within 4 points) = {sim['points_off'] <= 4.0}")
    log()

    con.close()

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "benchmark_output.txt").write_text("\n".join(OUT) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

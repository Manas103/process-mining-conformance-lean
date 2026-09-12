"""Runs all five claims end to end against a freshly generated 120,000-event
log and prints/records the measured numbers. This is the single script
behind docs/benchmark_output.txt.

Usage: .venv\\Scripts\\python.exe scripts\\run_benchmarks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pm import db as pmdb  # noqa: E402
from pm import reference as ref  # noqa: E402
from pm.conformance import check_conformance  # noqa: E402
from pm.cycle_time import locate_bottleneck_handoff, per_case_handoff_minutes, total_cycle_time_minutes  # noqa: E402
from pm.discovery import discover_directly_follows, dominant_edges, discovery_matches_documented_procedure  # noqa: E402
from pm.generator import generate_clean_only_log, generate_log  # noqa: E402
from pm.simulation import predict_and_validate  # noqa: E402

OUT = []


def log(line: str = "") -> None:
    print(line)
    OUT.append(line)


def main() -> int:
    log_df, case_meta_df = generate_log()
    con = pmdb.connect()
    pmdb.load_event_log(con, log_df)

    log("Claim 1: 120,000 workflow events.")
    log(f"MEASURED: {len(log_df)} events across {len(case_meta_df)} cases")
    log(f"meets_claim = {len(log_df) == 120000}")
    log()

    log("Claim 2: 24 of 24 seeded deviations from the documented procedure caught.")
    result = check_conformance(con)
    merged = result.merge(case_meta_df, on="case_id")
    seeded = merged[merged["deviation_category"] != "clean"]
    caught = seeded[~seeded["is_conformant"]]
    log(f"seeded deviation cases: {len(seeded)}")
    log(f"MEASURED: {len(caught)} of {len(seeded)} caught")
    log(f"meets_claim = {len(caught) == 24}")
    log()

    log("Claim 3: 0 false flags over 20 clean runs.")
    total_cases = 0
    total_false = 0
    for i in range(20):
        clean_log = generate_clean_only_log(seed=900_000 + i, n_cases=200)
        c2 = pmdb.connect()
        pmdb.load_event_log(c2, clean_log)
        r2 = check_conformance(c2)
        c2.close()
        total_cases += len(r2)
        total_false += int((~r2["is_conformant"]).sum())
    log(f"MEASURED: {total_false} false flags over {total_cases} clean cases across 20 runs")
    log(f"meets_claim = {total_false == 0}")
    log()

    log("Claim 4: located the handoff holding the largest share of median cycle time (design target: 41%).")
    conformant_ids = set(result.loc[result["is_conformant"], "case_id"])
    handoff_minutes = per_case_handoff_minutes(log_df, conformant_ids)
    total_minutes = total_cycle_time_minutes(log_df, conformant_ids)
    summary = locate_bottleneck_handoff(handoff_minutes, total_minutes)
    top = summary.iloc[0]
    log(summary.to_string(index=False))
    log(f"MEASURED bottleneck: {top['from_activity']} -> {top['to_activity']}, "
        f"{top['pct_of_median_total_cycle_time']:.1f}% of median cycle time "
        f"({top['median_total_cycle_time_minutes']:.1f} minutes)")
    log("meets_claim = n/a (design target was 41%; reported here is what was measured, not tuned to match)")
    log()

    log("Claim 5: simulation predicted a median cycle-time cut, confirmed within 4 points by a held-out replay "
        "(design target: predicted 27%).")
    sim = predict_and_validate(log_df, conformant_ids)
    for k, v in sim.items():
        log(f"  {k} = {v}")
    log(f"MEASURED: predicted {sim['predicted_pct_cut']:.2f}% on the fit half "
        f"({sim['fit_case_count']} cases), actual {sim['actual_pct_cut_on_holdout']:.2f}% on the held-out half "
        f"({sim['holdout_case_count']} cases), {sim['points_off']:.2f} points off")
    log(f"meets_claim (within 4 points) = {sim['points_off'] <= 4.0}")
    log()

    log("Bonus (not a resume claim, validation of the discovery module): "
        "directly-follows miner recovers the documented 7-edge procedure exactly.")
    edges = discover_directly_follows(con, min_support=5)
    discovered = dominant_edges(edges, dominance_threshold=0.9)
    exact, missing, extra = discovery_matches_documented_procedure(discovered, set(ref.ALLOWED_TRANSITIONS))
    log(f"MEASURED: exact_match={exact} missing={missing} extra={extra}")

    con.close()

    docs = Path(__file__).resolve().parent.parent / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "benchmark_output.txt").write_text("\n".join(OUT) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

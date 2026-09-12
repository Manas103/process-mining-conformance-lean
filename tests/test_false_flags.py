from __future__ import annotations

from pm import db as pmdb
from pm.conformance import check_conformance
from pm.generator import generate_clean_only_log


def test_0_false_flags_over_20_clean_runs():
    """20 independently generated, entirely deviation-free batches (each its
    own seed, so a genuinely different batch, not the same one 20 times).
    Every one must come back 100% conformant."""
    total_cases = 0
    total_false_flags = 0
    for run_idx in range(20):
        seed = 900_000 + run_idx
        log_df = generate_clean_only_log(seed=seed, n_cases=200)
        con = pmdb.connect()
        try:
            pmdb.load_event_log(con, log_df)
            result = check_conformance(con)
        finally:
            con.close()
        total_cases += len(result)
        total_false_flags += int((~result["is_conformant"]).sum())

    assert total_cases == 20 * 200
    assert total_false_flags == 0, f"{total_false_flags} false flags over {total_cases} clean cases"

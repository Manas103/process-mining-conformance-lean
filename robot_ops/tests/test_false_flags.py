from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
BASE_REPO = HERE.parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(BASE_REPO / "src"))

from pm import db as pm_db  # noqa: E402
from ro.ro_conformance import check_conformance  # noqa: E402
from ro.ro_generator import generate_clean_only_log  # noqa: E402


def test_0_false_flags_over_20_clean_runs():
    """20 independently generated, entirely deviation-free batches (each
    its own seed). Every one must come back 100% conformant."""
    total_cases = 0
    total_false_flags = 0
    for run_idx in range(20):
        seed = 700_000 + run_idx
        log_df = generate_clean_only_log(seed=seed, n_cases=200)
        con = pm_db.connect()
        try:
            pm_db.load_event_log(con, log_df)
            result = check_conformance(con)
        finally:
            con.close()
        total_cases += len(result)
        total_false_flags += int((~result["is_conformant"]).sum())

    assert total_cases == 20 * 200
    assert total_false_flags == 0, f"{total_false_flags} false flags over {total_cases} clean cases"

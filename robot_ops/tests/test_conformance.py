from __future__ import annotations

import pandas as pd

from ro.ro_conformance import check_conformance
from ro.ro_oracle import check_conformance_oracle


def test_24_of_24_seeded_deviations_caught(con, full_log):
    _, case_meta_df = full_log
    result = check_conformance(con)

    merged = result.merge(case_meta_df, on="case_id")
    seeded = merged[merged["deviation_category"] != "clean"]
    assert len(seeded) == 24

    caught = seeded[~seeded["is_conformant"]]
    assert len(caught) == 24, f"expected all 24 seeded deviations flagged, got {len(caught)}"

    mismatches = seeded[seeded["deviation_type"] != seeded["deviation_category"]]
    assert len(mismatches) == 0, mismatches[["case_id", "deviation_category", "deviation_type"]]


def test_conformant_case_count_is_the_remaining_23976(con, full_log):
    result = check_conformance(con)
    assert result["is_conformant"].sum() == 23976


def test_real_engine_agrees_with_independent_pure_python_oracle_over_the_full_log(con, full_log):
    log_df, _ = full_log
    real = check_conformance(con).set_index("case_id")

    events = log_df.to_dict("records")
    oracle_raw = check_conformance_oracle(events)
    oracle = {cid: (conf, dev) for cid, (conf, dev) in oracle_raw.items()}

    assert set(real.index) == set(oracle.keys())
    disagreements = []
    for case_id, row in real.iterrows():
        oracle_conf, oracle_dev = oracle[case_id]
        real_dev = None if pd.isna(row["deviation_type"]) else row["deviation_type"]
        if bool(row["is_conformant"]) != oracle_conf or real_dev != oracle_dev:
            disagreements.append((case_id, row["is_conformant"], real_dev, oracle_conf, oracle_dev))
    assert disagreements == [], f"{len(disagreements)} disagreements, e.g. {disagreements[:5]}"

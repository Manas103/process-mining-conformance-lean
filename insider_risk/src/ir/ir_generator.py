"""Seeded synthetic insider-risk case-log generator. Builds 20,000 cases,
each walking the 6-stage CASE_SEQUENCE exactly (no seeded process
deviations here; this extension is about cycle time, detection performance
and privacy-preserving reporting, not conformance checking, which the base
repo already covers). 20,000 cases * 6 stages = 120,000 events.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from . import ir_reference as ref

Event = tuple[str, dt.datetime, str]


def _choose_rule(rng: np.random.Generator) -> str:
    rules = ref.DETECTION_RULES
    weights = np.array([ref.RULE_WEIGHT[r] for r in rules], dtype=float)
    weights /= weights.sum()
    return rules[int(rng.choice(len(rules), p=weights))]


def _walk_sequence(arrival: dt.datetime, rng: np.random.Generator) -> dict[str, dt.datetime]:
    seq = ref.CASE_SEQUENCE
    t = {seq[0]: arrival}
    for j in range(len(seq) - 1):
        a, b = seq[j], seq[j + 1]
        shape, scale = ref.HANDOFF_GAMMA_PARAMS_MINUTES[(a, b)]
        t[b] = t[a] + dt.timedelta(minutes=float(rng.gamma(shape, scale)))
    return t


def generate_case_log(seed: int = ref.SEED, n_cases: int = ref.N_CASES) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (event_log_df, case_meta_df).

    event_log_df columns: case_id, activity, timestamp, resource, event_id
    (the same schema pm.db.load_event_log already expects).
    case_meta_df columns: case_id, detection_rule, analyst, substantiated,
    referral_date.
    """
    rng = np.random.default_rng(seed)

    gaps = rng.exponential(scale=ref.MEAN_INTERARRIVAL_MINUTES, size=n_cases)
    offsets_minutes = np.cumsum(gaps)
    arrival_times = [ref.SIM_START + dt.timedelta(minutes=float(m)) for m in offsets_minutes]

    rows: list[dict] = []
    case_meta: list[dict] = []
    event_id = 0

    for idx in range(n_cases):
        case_id = f"IR_CASE_{idx:06d}"
        arrival = arrival_times[idx]
        rule = _choose_rule(rng)
        analyst = ref.ANALYST_POOL[int(rng.integers(0, len(ref.ANALYST_POOL)))]
        substantiated = bool(rng.random() < ref.RULE_SUBSTANTIATION_RATE[rule])

        t = _walk_sequence(arrival, rng)
        for activity in ref.CASE_SEQUENCE:
            event_id += 1
            rows.append({
                "case_id": case_id,
                "activity": activity,
                "timestamp": t[activity],
                "resource": analyst,
                "event_id": event_id,
            })

        case_meta.append({
            "case_id": case_id,
            "detection_rule": rule,
            "analyst": analyst,
            "substantiated": substantiated,
            "referral_date": arrival.date().isoformat(),
        })

    log_df = pd.DataFrame(rows, columns=ref.EVENT_LOG_COLUMNS)
    log_df["timestamp"] = pd.to_datetime(log_df["timestamp"]).dt.floor(ref.TIMESTAMP_ROUND)

    perm = rng.permutation(len(log_df))
    log_df = log_df.iloc[perm].reset_index(drop=True)

    case_meta_df = pd.DataFrame(case_meta, columns=["case_id", "detection_rule", "analyst", "substantiated", "referral_date"])
    return log_df, case_meta_df

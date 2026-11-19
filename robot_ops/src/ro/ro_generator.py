"""Seeded synthetic session-log generator for the robot-operations
extension. Builds 24,000 data-collection sessions ("cases") of the
documented 5-stage lifecycle in ro_reference.CASE_SEQUENCE: 23,976 follow
it exactly; 24 are seeded with a single, genuine deviation each (8
missing-stage, 8 out-of-order, 8 extra/unauthorized-step, split 4
brand-new-activity / 4 duplicated-activity). Total events:
23,976*5 + 8*4 + 8*5 + 4*6 + 4*6 = 119,880 + 32 + 40 + 24 + 24 = 120,000.

This module is a direct re-point of the base repo's generator.py: same
timestamp-flooring and event_id discipline (see that module's own
docstring for why both matter), same deviation-category split, different
domain and different gated handoff.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from . import ro_reference as ref
from .ro_upload import next_upload_asis

Event = tuple[str, dt.datetime, str]


def _assign_resource(activity: str, rng: np.random.Generator) -> str:
    pool = ref.RESOURCE_POOL[ref.ACTIVITY_ROLE[activity]]
    return pool[int(rng.integers(0, len(pool)))]


def _walk_sequence(
    arrival_time: dt.datetime,
    rng: np.random.Generator,
    override_index: int | None = None,
    override_gap_seconds: float | None = None,
) -> dict[str, dt.datetime]:
    seq = ref.CASE_SEQUENCE
    t = {seq[0]: arrival_time}
    for j in range(len(seq) - 1):
        a, b = seq[j], seq[j + 1]
        if j == override_index:
            t[b] = t[a] + dt.timedelta(seconds=override_gap_seconds)
        elif (a, b) == ("Episode Validated", "Episode Uploaded"):
            t[b] = next_upload_asis(t[a])
        else:
            shape, scale = ref.HANDOFF_GAMMA_PARAMS_MINUTES[(a, b)]
            t[b] = t[a] + dt.timedelta(minutes=float(rng.gamma(shape, scale)))
    return t


def build_clean_case(arrival: dt.datetime, rng: np.random.Generator) -> list[Event]:
    t = _walk_sequence(arrival, rng)
    return [(a, t[a], _assign_resource(a, rng)) for a in ref.CASE_SEQUENCE]


def build_skip_case(arrival: dt.datetime, rng: np.random.Generator, skip_activity: str) -> list[Event]:
    t = _walk_sequence(arrival, rng)
    return [(a, t[a], _assign_resource(a, rng)) for a in ref.CASE_SEQUENCE if a != skip_activity]


def build_reorder_case(
    arrival: dt.datetime, rng: np.random.Generator, pair_index: int, gap_seconds: float
) -> list[Event]:
    seq = ref.CASE_SEQUENCE
    a, b = seq[pair_index], seq[pair_index + 1]
    t = _walk_sequence(arrival, rng, override_index=pair_index, override_gap_seconds=gap_seconds)
    early, late = t[a], t[b]
    t[a], t[b] = late, early
    true_order: list[str] = []
    for act in seq:
        if act == a:
            continue
        if act == b:
            true_order.append(b)
            true_order.append(a)
        else:
            true_order.append(act)
    return [(act, t[act], _assign_resource(act, rng)) for act in true_order]


def build_extra_new_case(
    arrival: dt.datetime, rng: np.random.Generator, insert_after: str, new_activity: str, new_role: str
) -> list[Event]:
    t = _walk_sequence(arrival, rng)
    seq = ref.CASE_SEQUENCE
    offset = float(rng.uniform(1, 8))
    new_time = t[insert_after] + dt.timedelta(minutes=offset)
    pool = ref.RESOURCE_POOL[new_role]
    new_resource = pool[int(rng.integers(0, len(pool)))]
    events: list[Event] = []
    for act in seq:
        events.append((act, t[act], _assign_resource(act, rng)))
        if act == insert_after:
            events.append((new_activity, new_time, new_resource))
    return events


def build_extra_duplicate_case(
    arrival: dt.datetime, rng: np.random.Generator, dup_activity: str
) -> list[Event]:
    t = _walk_sequence(arrival, rng)
    seq = ref.CASE_SEQUENCE
    offset = float(rng.uniform(1, 8))
    dup_time = t[dup_activity] + dt.timedelta(minutes=offset)
    dup_resource = _assign_resource(dup_activity, rng)
    events: list[Event] = []
    for act in seq:
        events.append((act, t[act], _assign_resource(act, rng)))
        if act == dup_activity:
            events.append((dup_activity, dup_time, dup_resource))
    return events


# The 24-case deviation plan: 8 missing-stage, 8 out-of-order, 8 extra/unauthorized-step.
def deviation_plan() -> list[dict]:
    skip_targets = [
        "Scene Reset", "Scene Reset", "Scene Reset",
        "Episode Recorded", "Episode Recorded", "Episode Recorded",
        "Episode Validated", "Episode Validated",
    ]
    reorder_pairs = [0, 0, 1, 1, 2, 2, 0, 1]  # pair index j means seq[j], seq[j+1]; excludes j=3 (the upload-gated pair)
    reorder_gap_seconds = [0, 0, 15, 30, 45, 60, 90, 120]  # two exact ties by design (see module docstring)
    extra_new = [
        ("Station Prepped", "Unscheduled Hardware Swap", "Operator"),
        ("Scene Reset", "Manual Scene Override", "Operator"),
        ("Episode Recorded", "Ad-Hoc Re-Record", "Operator"),
        ("Episode Validated", "Unlogged Re-Validation", "QA"),
    ]
    extra_dup = ["Scene Reset", "Episode Recorded", "Episode Validated", "Station Prepped"]

    plan: list[dict] = []
    for target in skip_targets:
        plan.append({"kind": "skip", "category": "missing_step", "skip_activity": target,
                     "detail": f"missing stage '{target}'"})
    for pair_idx, gap in zip(reorder_pairs, reorder_gap_seconds):
        a, b = ref.CASE_SEQUENCE[pair_idx], ref.CASE_SEQUENCE[pair_idx + 1]
        plan.append({"kind": "reorder", "category": "out_of_order", "pair_index": pair_idx, "gap_seconds": gap,
                     "detail": f"swapped '{a}' and '{b}' (gap {gap}s)"})
    for insert_after, name, role in extra_new:
        plan.append({"kind": "extra_new", "category": "unauthorized_step", "insert_after": insert_after,
                     "new_activity": name, "new_role": role,
                     "detail": f"inserted unauthorized activity '{name}' after '{insert_after}'"})
    for dup in extra_dup:
        plan.append({"kind": "extra_dup", "category": "unauthorized_step", "dup_activity": dup,
                     "detail": f"duplicated stage '{dup}'"})
    assert len(plan) == ref.N_DEVIATION_CASES
    return plan


def _build_from_plan_item(item: dict, arrival: dt.datetime, rng: np.random.Generator) -> list[Event]:
    if item["kind"] == "skip":
        return build_skip_case(arrival, rng, item["skip_activity"])
    if item["kind"] == "reorder":
        return build_reorder_case(arrival, rng, item["pair_index"], item["gap_seconds"])
    if item["kind"] == "extra_new":
        return build_extra_new_case(arrival, rng, item["insert_after"], item["new_activity"], item["new_role"])
    if item["kind"] == "extra_dup":
        return build_extra_duplicate_case(arrival, rng, item["dup_activity"])
    raise ValueError(f"unknown plan item kind: {item['kind']}")


def generate_log(seed: int = ref.SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (event_log_df, case_meta_df)."""
    rng = np.random.default_rng(seed)

    gaps = rng.exponential(scale=ref.MEAN_INTERARRIVAL_MINUTES, size=ref.TOTAL_CASES)
    offsets_minutes = np.cumsum(gaps)
    arrival_times = [ref.SIM_START + dt.timedelta(minutes=float(m)) for m in offsets_minutes]

    dev_positions = set(int(i) for i in rng.choice(ref.TOTAL_CASES, size=ref.N_DEVIATION_CASES, replace=False))
    plan = deviation_plan()
    dev_position_list = sorted(dev_positions)
    position_to_plan_item = dict(zip(dev_position_list, plan))

    rows: list[dict] = []
    case_meta: list[dict] = []
    event_id = 0

    for idx in range(ref.TOTAL_CASES):
        case_id = f"SESSION_{idx:06d}"
        arrival = arrival_times[idx]
        if idx in position_to_plan_item:
            item = position_to_plan_item[idx]
            events = _build_from_plan_item(item, arrival, rng)
            category, detail = item["category"], item["detail"]
        else:
            events = build_clean_case(arrival, rng)
            category, detail = "clean", ""

        for activity, timestamp, resource in events:
            event_id += 1
            rows.append({
                "case_id": case_id,
                "activity": activity,
                "timestamp": timestamp,
                "resource": resource,
                "event_id": event_id,
            })
        case_meta.append({"case_id": case_id, "deviation_category": category, "deviation_detail": detail})

    log_df = pd.DataFrame(rows, columns=ref.EVENT_LOG_COLUMNS)
    log_df["timestamp"] = pd.to_datetime(log_df["timestamp"]).dt.floor(ref.TIMESTAMP_ROUND)

    perm = rng.permutation(len(log_df))
    log_df = log_df.iloc[perm].reset_index(drop=True)

    case_meta_df = pd.DataFrame(case_meta, columns=["case_id", "deviation_category", "deviation_detail"])
    return log_df, case_meta_df


def generate_clean_only_log(seed: int, n_cases: int = 200) -> pd.DataFrame:
    """A small, entirely deviation-free batch, used by the
    0-false-flags-over-20-clean-runs check."""
    rng = np.random.default_rng(seed)
    gaps = rng.exponential(scale=ref.MEAN_INTERARRIVAL_MINUTES, size=n_cases)
    offsets_minutes = np.cumsum(gaps)
    arrival_times = [ref.SIM_START + dt.timedelta(minutes=float(m)) for m in offsets_minutes]

    rows: list[dict] = []
    event_id = 0
    for idx in range(n_cases):
        case_id = f"CLEAN_{seed}_{idx:05d}"
        events = build_clean_case(arrival_times[idx], rng)
        for activity, timestamp, resource in events:
            event_id += 1
            rows.append({
                "case_id": case_id, "activity": activity, "timestamp": timestamp,
                "resource": resource, "event_id": event_id,
            })
    log_df = pd.DataFrame(rows, columns=ref.EVENT_LOG_COLUMNS)
    log_df["timestamp"] = pd.to_datetime(log_df["timestamp"]).dt.floor(ref.TIMESTAMP_ROUND)
    return log_df

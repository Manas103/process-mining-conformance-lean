"""An independent, pure-Python reference for the per-case handoff
decomposition: no pandas, no DuckDB, no import of ir_cycle_time. Takes
plain dict rows and reimplements the same stage-to-stage minute
computation from scratch, diffed exactly against the real engine over the
full case population."""

from __future__ import annotations

from . import ir_reference as ref

HANDOFFS = list(zip(ref.CASE_SEQUENCE[:-1], ref.CASE_SEQUENCE[1:]))


def decompose_oracle(rows: list[dict]) -> dict[str, dict[str, float]]:
    """rows: list of {case_id, activity, timestamp, resource, event_id}.
    Returns {case_id: {"<a>__to__<b>": minutes, ..., "total_minutes": m}}."""
    by_case: dict[str, dict[str, object]] = {}
    for row in rows:
        by_case.setdefault(row["case_id"], {})[row["activity"]] = row["timestamp"]

    out: dict[str, dict[str, float]] = {}
    for case_id, stage_times in by_case.items():
        result: dict[str, float] = {}
        for a, b in HANDOFFS:
            delta = stage_times[b] - stage_times[a]
            result[f"{a}__to__{b}"] = delta.total_seconds() / 60.0
        total = stage_times[ref.CASE_SEQUENCE[-1]] - stage_times[ref.CASE_SEQUENCE[0]]
        result["total_minutes"] = total.total_seconds() / 60.0
        out[case_id] = result
    return out

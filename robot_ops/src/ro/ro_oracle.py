"""Independent, pure-Python conformance oracle for the robot-operations
extension. No duckdb, no pandas, no import of ro_conformance.py. Diffed
exactly against the DuckDB-SQL implementation in
tests/test_conformance.py.
"""

from __future__ import annotations

from . import ro_reference as ref

CASE_SEQUENCE = list(ref.CASE_SEQUENCE)
CASE_SET = set(CASE_SEQUENCE)
ALLOWED_TRANSITIONS = set(ref.ALLOWED_TRANSITIONS)


def check_conformance_oracle(events: list[dict]) -> dict[str, tuple[bool, str | None]]:
    """Returns {case_id: (is_conformant, deviation_type_or_None)}."""
    cases: dict[str, list[dict]] = {}
    for ev in events:
        cases.setdefault(ev["case_id"], []).append(ev)

    result: dict[str, tuple[bool, str | None]] = {}
    for case_id, evs in cases.items():
        evs_sorted = sorted(evs, key=lambda e: (e["timestamp"], e["event_id"]))
        activities = [e["activity"] for e in evs_sorted]

        counts: dict[str, int] = {}
        for a in activities:
            counts[a] = counts.get(a, 0) + 1

        missing = [a for a in CASE_SEQUENCE if counts.get(a, 0) == 0]
        has_extra = any(a not in CASE_SET for a in activities)
        has_duplicate = any(c > 1 for c in counts.values())

        if missing:
            result[case_id] = (False, "missing_step")
            continue
        if has_extra or has_duplicate:
            result[case_id] = (False, "unauthorized_step")
            continue

        ok = True
        for i in range(len(activities) - 1):
            if (activities[i], activities[i + 1]) not in ALLOWED_TRANSITIONS:
                ok = False
                break
        result[case_id] = (True, None) if ok else (False, "out_of_order")

    return result

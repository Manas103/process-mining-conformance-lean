"""Process discovery: a directly-follows-graph miner, nothing more.

This is honestly scoped. A directly-follows miner counts, over the whole
log, how often each activity is immediately followed by each other activity,
and calls an edge "discovered" once it clears a support threshold. It is NOT
a full alpha-miner or inductive-miner: it has no notion of parallel-split
(AND) versus exclusive-choice (XOR) gateways, cannot represent loops beyond
"this edge exists", and cannot distinguish "B always follows A" from "B
follows A most of the time, with rare skips" beyond the raw edge frequency.
For a strictly linear documented procedure (this project's
REFERENCE_SEQUENCE has exactly one allowed transition out of every step) that
limitation does not matter: discovery either recovers the documented chain
edge for edge, or it does not, and the seeded deviations are exactly the
kind of noise a support threshold is supposed to filter as non-dominant.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def discover_directly_follows(
    con: duckdb.DuckDBPyConnection, table: str = "events", min_support: int = 5
) -> pd.DataFrame:
    """Returns one row per (from_activity, to_activity) directly-follows edge
    observed at least once, with its raw count and the fraction of that
    from_activity's outgoing transitions it accounts for. use_event_id
    tiebreak matches conformance.py's ordering exactly, for the same reason
    (see reference.py / generator.py module docstrings)."""
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW dfg_pairs AS
        SELECT
            case_id,
            activity AS from_activity,
            LEAD(activity) OVER (PARTITION BY case_id ORDER BY timestamp, event_id) AS to_activity
        FROM {table}
        """
    )
    edges = con.execute(
        """
        SELECT from_activity, to_activity, COUNT(*) AS n
        FROM dfg_pairs
        WHERE to_activity IS NOT NULL
        GROUP BY from_activity, to_activity
        """
    ).fetchdf()

    totals = edges.groupby("from_activity")["n"].transform("sum")
    edges["fraction_of_from_activity"] = edges["n"] / totals
    edges = edges[edges["n"] >= min_support].sort_values(
        ["from_activity", "n"], ascending=[True, False]
    ).reset_index(drop=True)
    return edges


def dominant_edges(edges: pd.DataFrame, dominance_threshold: float = 0.9) -> set[tuple[str, str]]:
    """The discovered as-is model: for each from_activity, the single edge
    that accounts for at least dominance_threshold of its outgoing mass. A
    from_activity with no edge clearing the threshold contributes none (the
    miner declines to guess when the log itself is ambiguous, rather than
    silently picking the plurality edge)."""
    result: set[tuple[str, str]] = set()
    for from_activity, group in edges.groupby("from_activity"):
        top = group.iloc[0]
        if top["fraction_of_from_activity"] >= dominance_threshold:
            result.add((from_activity, top["to_activity"]))
    return result


def discovery_matches_documented_procedure(
    discovered: set[tuple[str, str]], documented: set[tuple[str, str]]
) -> tuple[bool, set[tuple[str, str]], set[tuple[str, str]]]:
    """(exact_match, missing_from_discovery, extra_in_discovery)."""
    missing = documented - discovered
    extra = discovered - documented
    return (not missing and not extra), missing, extra

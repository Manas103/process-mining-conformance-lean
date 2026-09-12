"""Conformance checking against the documented reference procedure. This is
the main implementation: real DuckDB SQL, diffed exactly against the
pure-Python oracle in oracle.py (see tests/test_oracle_diff.py and
scripts/run_oracle_diff.py).

A case is conformant only if its activity multiset exactly equals the
documented REFERENCE_SEQUENCE and its events, sorted into per-case order,
occur in exactly that sequence. Any violation is classified into exactly one
of three deviation types, checked in this fixed priority order:

1. missing_step: at least one documented activity never occurs in the case.
2. unauthorized_step: an activity occurs that is not in the documented
   procedure, or a documented activity occurs more than once.
3. out_of_order: the case has the correct activity multiset, but a
   consecutive pair, in per-case order, is not an allowed transition.

use_event_id_tiebreak controls how a case's events are ordered when two
events share an identical persisted timestamp (see reference.py and
generator.py for why that happens, and the README Findings section for the
bug the naive tiebreak-free ordering caused). It defaults to True (the
fixed behavior); pass False to reproduce the original bug.
"""

from __future__ import annotations

import pandas as pd
import duckdb

from . import reference as ref


def _order_by_clause(use_event_id_tiebreak: bool) -> str:
    return "timestamp, event_id" if use_event_id_tiebreak else "timestamp"


def check_conformance(
    con: duckdb.DuckDBPyConnection,
    table: str = "events",
    use_event_id_tiebreak: bool = True,
) -> pd.DataFrame:
    reference_activities = pd.DataFrame({"activity": ref.REFERENCE_SEQUENCE})
    allowed_transitions = pd.DataFrame(
        sorted(ref.ALLOWED_TRANSITIONS), columns=["from_activity", "to_activity"]
    )
    con.register("reference_activities_view", reference_activities)
    con.register("allowed_transitions_view", allowed_transitions)
    con.execute("DROP TABLE IF EXISTS reference_activities")
    con.execute("DROP TABLE IF EXISTS allowed_transitions")
    con.execute("CREATE TABLE reference_activities AS SELECT * FROM reference_activities_view")
    con.execute("CREATE TABLE allowed_transitions AS SELECT * FROM allowed_transitions_view")
    con.unregister("reference_activities_view")
    con.unregister("allowed_transitions_view")

    order_clause = _order_by_clause(use_event_id_tiebreak)

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW activity_counts AS
        SELECT case_id, activity, COUNT(*) AS n
        FROM {table}
        GROUP BY case_id, activity
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW all_case_ids AS
        SELECT DISTINCT case_id FROM events
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW missing_by_case AS
        SELECT c.case_id, COUNT(*) AS n_missing
        FROM all_case_ids c
        CROSS JOIN reference_activities ra
        LEFT JOIN activity_counts ac ON ac.case_id = c.case_id AND ac.activity = ra.activity
        WHERE ac.activity IS NULL
        GROUP BY c.case_id
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW unauthorized_by_case AS
        SELECT DISTINCT ac.case_id
        FROM activity_counts ac
        LEFT JOIN reference_activities ra ON ra.activity = ac.activity
        WHERE ra.activity IS NULL OR ac.n > 1
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW ordered_events AS
        SELECT
            case_id,
            activity,
            LEAD(activity) OVER (PARTITION BY case_id ORDER BY {order_clause}) AS next_activity
        FROM {table}
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW out_of_order_by_case AS
        SELECT DISTINCT oe.case_id
        FROM ordered_events oe
        LEFT JOIN allowed_transitions allowed
            ON allowed.from_activity = oe.activity AND allowed.to_activity = oe.next_activity
        WHERE oe.next_activity IS NOT NULL
          AND allowed.from_activity IS NULL
          -- only meaningful for cases whose activity set already matches the
          -- documented procedure exactly; missing/unauthorized cases are
          -- classified by the higher-priority checks above regardless of
          -- what this view says about them
        """
    )

    result = con.execute(
        """
        SELECT
            c.case_id,
            CASE
                WHEN m.case_id IS NOT NULL THEN 'missing_step'
                WHEN u.case_id IS NOT NULL THEN 'unauthorized_step'
                WHEN o.case_id IS NOT NULL THEN 'out_of_order'
                ELSE NULL
            END AS deviation_type
        FROM all_case_ids c
        LEFT JOIN missing_by_case m ON m.case_id = c.case_id
        LEFT JOIN unauthorized_by_case u ON u.case_id = c.case_id
        LEFT JOIN out_of_order_by_case o ON o.case_id = c.case_id
        ORDER BY c.case_id
        """
    ).fetchdf()

    result["is_conformant"] = result["deviation_type"].isna()
    return result[["case_id", "is_conformant", "deviation_type"]]

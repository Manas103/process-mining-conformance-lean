"""Conformance checking against the documented robot-operations session
lifecycle. Real DuckDB SQL, diffed exactly against the pure-Python oracle
in ro_oracle.py. This is the base repo's conformance.py re-pointed at
CASE_SEQUENCE instead of REFERENCE_SEQUENCE; the classification logic and
the event_id tiebreak discipline are unchanged.

A case is conformant only if its activity multiset exactly equals
CASE_SEQUENCE and its events, sorted into per-case order, occur in exactly
that sequence. Any violation is classified into exactly one of three
deviation types, checked in this fixed priority order:

1. missing_step: at least one documented stage never occurs in the case.
2. unauthorized_step: a stage occurs that is not in the documented
   lifecycle, or a documented stage occurs more than once.
3. out_of_order: the case has the correct activity multiset, but a
   consecutive pair, in per-case order, is not an allowed transition.
"""

from __future__ import annotations

import pandas as pd
import duckdb

from . import ro_reference as ref


def _order_by_clause(use_event_id_tiebreak: bool) -> str:
    return "timestamp, event_id" if use_event_id_tiebreak else "timestamp"


def check_conformance(
    con: duckdb.DuckDBPyConnection,
    table: str = "events",
    use_event_id_tiebreak: bool = True,
) -> pd.DataFrame:
    reference_activities = pd.DataFrame({"activity": ref.CASE_SEQUENCE})
    allowed_transitions = pd.DataFrame(
        sorted(ref.ALLOWED_TRANSITIONS), columns=["from_activity", "to_activity"]
    )
    con.register("reference_activities_view", reference_activities)
    con.register("allowed_transitions_view", allowed_transitions)
    con.execute("DROP TABLE IF EXISTS ro_reference_activities")
    con.execute("DROP TABLE IF EXISTS ro_allowed_transitions")
    con.execute("CREATE TABLE ro_reference_activities AS SELECT * FROM reference_activities_view")
    con.execute("CREATE TABLE ro_allowed_transitions AS SELECT * FROM allowed_transitions_view")
    con.unregister("reference_activities_view")
    con.unregister("allowed_transitions_view")

    order_clause = _order_by_clause(use_event_id_tiebreak)

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW ro_activity_counts AS
        SELECT case_id, activity, COUNT(*) AS n
        FROM {table}
        GROUP BY case_id, activity
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW ro_all_case_ids AS
        SELECT DISTINCT case_id FROM {table}
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW ro_missing_by_case AS
        SELECT c.case_id, COUNT(*) AS n_missing
        FROM ro_all_case_ids c
        CROSS JOIN ro_reference_activities ra
        LEFT JOIN ro_activity_counts ac ON ac.case_id = c.case_id AND ac.activity = ra.activity
        WHERE ac.activity IS NULL
        GROUP BY c.case_id
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW ro_unauthorized_by_case AS
        SELECT DISTINCT ac.case_id
        FROM ro_activity_counts ac
        LEFT JOIN ro_reference_activities ra ON ra.activity = ac.activity
        WHERE ra.activity IS NULL OR ac.n > 1
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW ro_ordered_events AS
        SELECT
            case_id,
            activity,
            LEAD(activity) OVER (PARTITION BY case_id ORDER BY {order_clause}) AS next_activity
        FROM {table}
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW ro_out_of_order_by_case AS
        SELECT DISTINCT oe.case_id
        FROM ro_ordered_events oe
        LEFT JOIN ro_allowed_transitions allowed
            ON allowed.from_activity = oe.activity AND allowed.to_activity = oe.next_activity
        WHERE oe.next_activity IS NOT NULL
          AND allowed.from_activity IS NULL
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
        FROM ro_all_case_ids c
        LEFT JOIN ro_missing_by_case m ON m.case_id = c.case_id
        LEFT JOIN ro_unauthorized_by_case u ON u.case_id = c.case_id
        LEFT JOIN ro_out_of_order_by_case o ON o.case_id = c.case_id
        ORDER BY c.case_id
        """
    ).fetchdf()

    result["is_conformant"] = result["deviation_type"].isna()
    return result[["case_id", "is_conformant", "deviation_type"]]

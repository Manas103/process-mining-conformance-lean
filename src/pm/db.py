"""DuckDB connection and schema helpers shared by discovery, conformance,
and cycle-time modules."""

from __future__ import annotations

import duckdb
import pandas as pd


def connect(path: str | None = None) -> duckdb.DuckDBPyConnection:
    """path=None opens an in-memory database; pass a file path for an
    on-disk .duckdb file."""
    return duckdb.connect(path or ":memory:")


def load_event_log(con: duckdb.DuckDBPyConnection, log_df: pd.DataFrame, table: str = "events") -> None:
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.register("log_df_view", log_df)
    con.execute(
        f"""
        CREATE TABLE {table} AS
        SELECT
            case_id,
            activity,
            timestamp,
            resource,
            event_id
        FROM log_df_view
        """
    )
    con.unregister("log_df_view")

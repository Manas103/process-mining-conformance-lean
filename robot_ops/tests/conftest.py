"""Generates the 120,000-event robot-operations session log once per test
session and loads it into an in-memory DuckDB connection via the base
repo's own pm.db (reused unmodified: its schema is already case_id/
activity/timestamp/resource/event_id, which is exactly what this
extension's log uses too)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
BASE_REPO = HERE.parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(BASE_REPO / "src"))

from pm import db as pm_db  # noqa: E402
from ro import ro_generator  # noqa: E402


@pytest.fixture(scope="session")
def full_log():
    log_df, case_meta_df = ro_generator.generate_log()
    return log_df, case_meta_df


@pytest.fixture()
def con(full_log):
    log_df, _ = full_log
    connection = pm_db.connect()
    pm_db.load_event_log(connection, log_df)
    yield connection
    connection.close()

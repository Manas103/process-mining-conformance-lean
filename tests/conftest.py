from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pm import db as pmdb  # noqa: E402
from pm.generator import generate_log  # noqa: E402


@pytest.fixture(scope="session")
def full_log():
    """Generated once per test session: 120,000 events, 15,000 cases, the
    same seed every run (pm.reference.SEED), so this fixture is itself
    deterministic across test runs."""
    log_df, case_meta_df = generate_log()
    return log_df, case_meta_df


@pytest.fixture()
def con(full_log):
    log_df, _ = full_log
    connection = pmdb.connect()
    pmdb.load_event_log(connection, log_df)
    yield connection
    connection.close()

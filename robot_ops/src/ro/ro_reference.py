"""Fixed constants for the robot-operations extension: the data-collection
session lifecycle, resource pools, handoff timing model, the upload-window
schedule (as-is and redesigned), and the 24-case deviation-seeding plan.
Nothing here is measured; everything else in this package checks reality
(the generated log) against it.

This extension re-points the base repo's own conformance-checking,
cycle-time and redesign-simulation engine (originally order-fulfillment) at
a robot data-collection session lifecycle: a station preps, the scene is
reset to a target initial condition, an episode is recorded, the episode is
validated, and the episode is uploaded. See robot_ops/README.md for why
this is an extension rather than a new repo.
"""

from __future__ import annotations

import datetime as dt

SEED = 20261119

CASE_SEQUENCE = [
    "Station Prepped",
    "Scene Reset",
    "Episode Recorded",
    "Episode Validated",
    "Episode Uploaded",
]

ACTIVITY_ROLE = {
    "Station Prepped": "Operator",
    "Scene Reset": "Operator",
    "Episode Recorded": "Operator",
    "Episode Validated": "QA",
    "Episode Uploaded": "DataOps",
}

RESOURCE_POOL = {
    "Operator": [f"Operator_{i}" for i in range(1, 7)],
    "QA": [f"QA_{i}" for i in range(1, 4)],
    "DataOps": [f"DataOps_{i}" for i in range(1, 3)],
}

# The documented procedure is a strict linear sequence: exactly one allowed
# transition out of each step. ALLOWED_TRANSITIONS is the directed edge set
# the conformance checker treats as "as-documented".
ALLOWED_TRANSITIONS = set(zip(CASE_SEQUENCE[:-1], CASE_SEQUENCE[1:]))

# Handoff wait-time model for every documented transition except
# ("Episode Validated", "Episode Uploaded"), which is governed by the
# upload-window schedule below, not a gamma draw. Values are (shape, scale)
# in minutes for a Gamma distribution; mean = shape * scale. Business-
# plausible station timings chosen up front and never adjusted afterward to
# hit a target number.
HANDOFF_GAMMA_PARAMS_MINUTES = {
    ("Station Prepped", "Scene Reset"): (3.0, 7.0),          # mean 21 min, positioning + calibration check
    ("Scene Reset", "Episode Recorded"): (2.0, 15.0),         # mean 30 min, the demonstration itself
    ("Episode Recorded", "Episode Validated"): (3.0, 15.0),   # mean 45 min, QA review queue
}

# Upload-window schedule (the seeded bottleneck): as-documented, episodes
# are batched and uploaded once a day at UPLOAD_HOUR_ASIS:00 to avoid
# saturating the lab network during active collection. Any episode
# validated before that hour waits until it; any episode validated after it
# waits until the next day's window. UPLOAD_PACKAGE_MINUTES is fixed
# packaging/encryption overhead logged between the window firing and the
# "Episode Uploaded" event itself.
UPLOAD_HOUR_ASIS = 22
UPLOAD_PACKAGE_MINUTES = 10

# Redesign under evaluation: parallelize the single daily upload into four
# upload windows spaced 6 hours apart, removing the batch-and-wait.
UPLOAD_INTERVAL_HOURS_REDESIGN = 6
UPLOAD_HOURS_REDESIGN = sorted(
    {(UPLOAD_HOUR_ASIS + k * UPLOAD_INTERVAL_HOURS_REDESIGN) % 24 for k in range(24 // UPLOAD_INTERVAL_HOURS_REDESIGN)}
)

# Timestamps are persisted to minute resolution, matching a realistic
# station-log granularity.
TIMESTAMP_ROUND = "min"

N_CLEAN_CASES = 23976
N_DEVIATION_CASES = 24  # 8 missing-stage + 8 out-of-order + 8 extra/unauthorized-step

SIM_START = dt.datetime(2026, 1, 5, 0, 0, 0)
SIM_HORIZON_DAYS = 300
TOTAL_CASES = N_CLEAN_CASES + N_DEVIATION_CASES
MEAN_INTERARRIVAL_MINUTES = (SIM_HORIZON_DAYS * 24 * 60) / TOTAL_CASES

# Unauthorized activities used by the extra-step deviation cases: not part
# of CASE_SEQUENCE, so any occurrence is, by definition, out of procedure.
UNAUTHORIZED_ACTIVITIES = {
    "Unscheduled Hardware Swap": "Operator",
    "Manual Scene Override": "Operator",
    "Ad-Hoc Re-Record": "Operator",
    "Unlogged Re-Validation": "QA",
}

EVENT_LOG_COLUMNS = ["case_id", "activity", "timestamp", "resource", "event_id"]

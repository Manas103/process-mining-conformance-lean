"""Fixed constants for the insider-risk extension: the case lifecycle,
detection-rule population, handoff timing model, and the small-cell
suppression threshold. Nothing here is measured; everything else in this
package checks reality (the generated log) against it or reports on it.

This extension re-points the base repo's per-case stage-decomposition
engine (originally an order-fulfillment process) at an insider-risk case
lifecycle, reusing pm.db unmodified; see insider_risk/README.md for why
this is an extension rather than a new repo.
"""

from __future__ import annotations

import datetime as dt

SEED = 20260912

CASE_SEQUENCE = [
    "Referral Received",
    "Triage Assigned",
    "Triage Completed",
    "Investigation Opened",
    "Evidence Reviewed",
    "Disposition Decided",
]

N_ANALYSTS = 20
ANALYST_POOL = [f"Analyst_{i:02d}" for i in range(1, N_ANALYSTS + 1)]

DETECTION_RULES = [
    "DLP-BulkExfil",
    "DLP-OffHoursUpload",
    "HR-Referral",
    "Anonymous-Tip",
    "Manager-Report",
    "Access-Anomaly",
]

# Business-plausible substantiation rate (true positive rate) per rule,
# chosen once up front and never adjusted afterward to hit a target number.
RULE_SUBSTANTIATION_RATE = {
    "DLP-BulkExfil": 0.35,
    "DLP-OffHoursUpload": 0.20,
    "HR-Referral": 0.55,
    "Anonymous-Tip": 0.15,
    "Manager-Report": 0.45,
    "Access-Anomaly": 0.25,
}

# Relative weight of how often each rule fires (not uniform: DLP rules fire
# far more often than a human referral does in a real program).
RULE_WEIGHT = {
    "DLP-BulkExfil": 30,
    "DLP-OffHoursUpload": 25,
    "HR-Referral": 8,
    "Anonymous-Tip": 5,
    "Manager-Report": 7,
    "Access-Anomaly": 25,
}

# Handoff wait-time model, (shape, scale) minutes for a Gamma distribution,
# mean = shape * scale. Triage Completed -> Investigation Opened is the
# seeded bottleneck (the investigation-opening backlog), sized so its mean
# is exactly as large as the other 4 handoffs combined, i.e. a 50% design
# target for its share of total cycle time.
HANDOFF_GAMMA_PARAMS_MINUTES = {
    ("Referral Received", "Triage Assigned"): (2.0, 20.0),         # mean 40 min, triage intake queue
    ("Triage Assigned", "Triage Completed"): (2.0, 30.0),          # mean 60 min, analyst working the triage
    ("Triage Completed", "Investigation Opened"): (5.0, 74.0),     # mean 370 min, investigation-opening backlog (the bottleneck)
    ("Investigation Opened", "Evidence Reviewed"): (3.0, 60.0),    # mean 180 min, evidence collection and review
    ("Evidence Reviewed", "Disposition Decided"): (2.0, 45.0),     # mean 90 min, adjudication
}

ALLOWED_TRANSITIONS = set(zip(CASE_SEQUENCE[:-1], CASE_SEQUENCE[1:]))

TIMESTAMP_ROUND = "min"

N_CASES = 20000
SIM_START = dt.datetime(2026, 1, 5, 0, 0, 0)
SIM_HORIZON_DAYS = 240
MEAN_INTERARRIVAL_MINUTES = (SIM_HORIZON_DAYS * 24 * 60) / N_CASES

# Small-cell suppression: an aggregate covering fewer than this many cases
# is never returned with its real count.
SUPPRESSION_THRESHOLD = 5

EVENT_LOG_COLUMNS = ["case_id", "activity", "timestamp", "resource", "event_id"]

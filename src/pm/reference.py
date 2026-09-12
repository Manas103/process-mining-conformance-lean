"""Every fixed constant for this project: the documented reference procedure,
resource pools, handoff timing model, the as-is and redesigned dispatch
schedules, and the deviation-seeding plan. Nothing here is measured; this is
the "as-documented" ground truth the rest of the package checks reality
against.

Process modeled: internal order-fulfillment, from an order landing in Sales
through the warehouse to Logistics dispatch and an internal close-out. It
deliberately stops at "Order Closed" (an internal system action taken once
the order has shipped and been invoiced) rather than waiting on a customer's
actual payment, so that every handoff measured is internal to the business
and could plausibly be redesigned; an external customer-payment wait would
trivially dominate cycle time and isn't a process defect this tool's kind of
Lean redesign could remove.
"""

from __future__ import annotations

import datetime as dt

SEED = 20260912  # today's date, used as the single source-of-truth seed

REFERENCE_SEQUENCE = [
    "Order Received",
    "Credit Check",
    "Inventory Allocation",
    "Pick Item",
    "Pack Item",
    "Ship Item",
    "Invoice Generated",
    "Order Closed",
]

ACTIVITY_ROLE = {
    "Order Received": "Sales",
    "Credit Check": "Finance",
    "Inventory Allocation": "Warehouse",
    "Pick Item": "Warehouse",
    "Pack Item": "Warehouse",
    "Ship Item": "Logistics",
    "Invoice Generated": "Finance",
    "Order Closed": "Sales",
}

RESOURCE_POOL = {
    "Sales": [f"Sales_{i}" for i in range(1, 6)],
    "Finance": [f"Finance_{i}" for i in range(1, 5)],
    "Warehouse": [f"Warehouse_{i}" for i in range(1, 7)],
    "Logistics": [f"Logistics_{i}" for i in range(1, 4)],
}

# The documented procedure is a strict linear sequence: exactly one allowed
# transition out of each step. ALLOWED_TRANSITIONS is the directed edge set
# the conformance checker treats as "as-documented".
ALLOWED_TRANSITIONS = set(zip(REFERENCE_SEQUENCE[:-1], REFERENCE_SEQUENCE[1:]))

# Handoff wait-time model for every documented transition except
# ("Pack Item", "Ship Item"), which is governed by the dispatch schedule
# below, not a gamma draw. Values are (shape, scale) in minutes for a Gamma
# distribution; mean = shape * scale. These are business-plausible queueing
# and processing times chosen up front and never adjusted to hit a target
# number afterward.
HANDOFF_GAMMA_PARAMS_MINUTES = {
    ("Order Received", "Credit Check"): (4.0, 60.0),        # mean 240 min, Finance intake queue
    ("Credit Check", "Inventory Allocation"): (3.0, 40.0),   # mean 120 min
    ("Inventory Allocation", "Pick Item"): (2.0, 30.0),      # mean 60 min
    ("Pick Item", "Pack Item"): (2.0, 45.0),                 # mean 90 min
    ("Ship Item", "Invoice Generated"): (3.0, 60.0),         # mean 180 min
    ("Invoice Generated", "Order Closed"): (2.0, 30.0),      # mean 60 min
}

# Dispatch schedule (the seeded bottleneck): as-documented, a single truck
# departs once a day at DISPATCH_HOUR_ASIS:00. Any order packed before that
# hour waits until it; any order packed after it waits until the next day's
# departure. DISPATCH_LOAD_MINUTES is fixed loading/paperwork overhead
# logged between the truck's departure and the "Ship Item" event itself.
DISPATCH_HOUR_ASIS = 17
DISPATCH_LOAD_MINUTES = 15

# Redesign under evaluation: parallelize the single daily dispatch into four
# dispatch windows spaced 6 hours apart, removing the batch-and-wait.
DISPATCH_INTERVAL_HOURS_REDESIGN = 6
DISPATCH_HOURS_REDESIGN = sorted(
    {(DISPATCH_HOUR_ASIS + k * DISPATCH_INTERVAL_HOURS_REDESIGN) % 24 for k in range(24 // DISPATCH_INTERVAL_HOURS_REDESIGN)}
)

# Timestamps are persisted to minute resolution, matching a realistic
# audit-log granularity (see README Findings for why this matters).
TIMESTAMP_ROUND = "min"

N_CLEAN_CASES = 14976
N_DEVIATION_CASES = 24  # 8 skipped-step + 8 out-of-order + 8 extra/unauthorized-step

SIM_START = dt.datetime(2026, 1, 5, 0, 0, 0)
SIM_HORIZON_DAYS = 300
# 15,000 total cases spread across the horizon by a Poisson arrival process.
TOTAL_CASES = N_CLEAN_CASES + N_DEVIATION_CASES
MEAN_INTERARRIVAL_MINUTES = (SIM_HORIZON_DAYS * 24 * 60) / TOTAL_CASES

# Unauthorized activities used by the extra-step deviation cases: not part of
# REFERENCE_SEQUENCE, so any occurrence is, by definition, out of procedure.
UNAUTHORIZED_ACTIVITIES = {
    "Manual Discount Override": "Sales",
    "Rush Shipping Request": "Logistics",
    "Unscheduled Inventory Recount": "Warehouse",
    "Credit Limit Exception Approval": "Finance",
}

EVENT_LOG_COLUMNS = ["case_id", "activity", "timestamp", "resource", "event_id"]

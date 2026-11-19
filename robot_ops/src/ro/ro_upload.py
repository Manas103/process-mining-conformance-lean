"""The Episode Uploaded gate: the one handoff not modeled as a gamma draw.

As-documented, DataOps batches validated episodes and uploads them once a
day, to avoid saturating the lab network during active collection. An
"Episode Validated" completion does not become an "Episode Uploaded" event
until the next scheduled window, plus a fixed packaging/encryption
overhead. This module is shared by the generator (which builds the as-is
120,000-event log under UPLOAD_HOUR_ASIS) and the simulator (which
re-applies the redesigned, four-times-a-day schedule to real Episode
Validated completion timestamps already in the log, never regenerating
them). This mirrors the base repo's dispatch.py exactly; only the gated
activity names and the schedule constants differ.
"""

from __future__ import annotations

import datetime as dt

from . import ro_reference as ref


def next_upload_asis(validated_time: dt.datetime) -> dt.datetime:
    """Next single daily upload window at UPLOAD_HOUR_ASIS:00 strictly
    after validated_time, plus fixed packaging overhead."""
    candidate = validated_time.replace(hour=ref.UPLOAD_HOUR_ASIS, minute=0, second=0, microsecond=0)
    if candidate <= validated_time:
        candidate += dt.timedelta(days=1)
    return candidate + dt.timedelta(minutes=ref.UPLOAD_PACKAGE_MINUTES)


def next_upload_redesign(validated_time: dt.datetime) -> dt.datetime:
    """Next window among the redesigned multi-window schedule strictly
    after validated_time, plus the same fixed packaging overhead."""
    day_start = validated_time.replace(hour=0, minute=0, second=0, microsecond=0)
    for offset_days in (0, 1):
        base = day_start + dt.timedelta(days=offset_days)
        for hour in ref.UPLOAD_HOURS_REDESIGN:
            candidate = base + dt.timedelta(hours=hour)
            if candidate > validated_time:
                return candidate + dt.timedelta(minutes=ref.UPLOAD_PACKAGE_MINUTES)
    raise RuntimeError("no redesigned upload window found within 2 days")

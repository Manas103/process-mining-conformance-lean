"""The Ship Item dispatch gate: the one handoff not modeled as a gamma draw.

As-documented, Logistics runs a single daily truck. A "Pack Item" completion
does not become a "Ship Item" event until the next scheduled departure, plus
a fixed loading overhead. This module is shared by the generator (which
builds the as-is 120,000-event log under DISPATCH_HOUR_ASIS) and the
simulator (which re-applies the redesigned, four-times-a-day schedule to
real Pack Item completion timestamps already in the log, never regenerating
them).
"""

from __future__ import annotations

import datetime as dt

from . import reference as ref


def next_dispatch_asis(pack_time: dt.datetime) -> dt.datetime:
    """Next single daily departure at DISPATCH_HOUR_ASIS:00 strictly after
    pack_time, plus fixed loading overhead."""
    candidate = pack_time.replace(hour=ref.DISPATCH_HOUR_ASIS, minute=0, second=0, microsecond=0)
    if candidate <= pack_time:
        candidate += dt.timedelta(days=1)
    return candidate + dt.timedelta(minutes=ref.DISPATCH_LOAD_MINUTES)


def next_dispatch_redesign(pack_time: dt.datetime) -> dt.datetime:
    """Next departure among the redesigned multi-window schedule strictly
    after pack_time, plus the same fixed loading overhead."""
    day_start = pack_time.replace(hour=0, minute=0, second=0, microsecond=0)
    for offset_days in (0, 1):
        base = day_start + dt.timedelta(days=offset_days)
        for hour in ref.DISPATCH_HOURS_REDESIGN:
            candidate = base + dt.timedelta(hours=hour)
            if candidate > pack_time:
                return candidate + dt.timedelta(minutes=ref.DISPATCH_LOAD_MINUTES)
    raise RuntimeError("no redesigned dispatch slot found within 2 days")

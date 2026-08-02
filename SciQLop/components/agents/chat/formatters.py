"""Pure display formatters for the session-info strip.

Kept free of Qt so the display rules are testable as plain functions — the
widgets in `info_bar.py` only join and place what `info_segments` returns.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import List, Optional

from ..backend import CarbonFootprint, Cost, Quota, UsageSnapshot


def fmt_tokens(n: Optional[int]) -> str:
    if n is None:
        return ""
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}k"
    return f"{n / 1_000_000:.2f}M"


def fmt_cost(cost: Optional[Cost]) -> str:
    if cost is None:
        return ""
    if cost.unit == "USD":
        return f"${cost.amount:.2f}"
    return f"{cost.amount:.2f} {cost.unit}"


def fmt_duration(ms: Optional[int]) -> str:
    if not ms:
        return ""
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds) // 60}m {int(seconds) % 60}s"


def fmt_reset_time(resets_at: Optional[float], now: Optional[float] = None) -> str:
    """A reset instant, qualified by weekday only when it is not today.

    "19:30" reads unambiguously for a 5-hour window; a weekly one lands days
    out, where a bare clock time would be misleading.
    """
    if not resets_at:
        return ""
    moment = datetime.fromtimestamp(resets_at)
    reference = datetime.fromtimestamp(now if now is not None else time.time())
    if moment.date() == reference.date():
        return moment.strftime("%H:%M")
    return moment.strftime("%a %H:%M")


def fmt_quota(quota: Optional[Quota], now: Optional[float] = None) -> str:
    """Consumption, not headroom: "5h 82%" is what a rate-limit window means."""
    if quota is None:
        return ""
    if quota.unlimited:
        return f"unlimited {quota.label}"
    if quota.percent_used is not None:
        reset = fmt_reset_time(quota.resets_at, now=now)
        used = f"{quota.label} {quota.percent_used:.0f}%"
        return f"{used} ↻{reset}" if reset else used
    if quota.remaining is not None:
        return f"{fmt_tokens(int(quota.remaining))} {quota.label} left"
    return ""


def fmt_carbon(carbon: Optional[CarbonFootprint]) -> str:
    if carbon is None:
        return ""
    if carbon.kg_co2eq is not None:
        grams = carbon.kg_co2eq * 1000.0
        if grams < 1000:
            return f"{grams:.1f} gCO₂eq"
        return f"{carbon.kg_co2eq:.2f} kgCO₂eq"
    if carbon.kwh is not None:
        return f"{carbon.kwh * 1000.0:.1f} Wh"
    return ""


def info_segments(
    snapshot: Optional[UsageSnapshot],
    effort: Optional[str] = None,
    now: Optional[float] = None,
) -> List[str]:
    """The strip's segments, in display order. Absent data yields no segment."""
    if snapshot is None:
        return []
    segments: List[str] = []
    if snapshot.model:
        segments.append(snapshot.model)
    if effort:
        segments.append(effort)
    total = snapshot.tokens.total if snapshot.tokens else None
    if total is not None:
        segments.append(fmt_tokens(total))
    percent = snapshot.context_percent
    if percent is not None:
        segments.append(f"{percent:.0f}%")
    cost = fmt_cost(snapshot.cost)
    if cost:
        segments.append(cost)
    for quota in snapshot.quotas:
        text = fmt_quota(quota, now=now)
        if text:
            segments.append(text)
    carbon = fmt_carbon(snapshot.carbon)
    if carbon:
        segments.append(carbon)
    return segments

"""Time-range duration presets: the sciqlop.time_presets extension point (Tier 3 spec §4.2).

The time-range bar's duration combo, the command palette's time-range completions and its duration table all
read this point. Zoom limits are not presets: they stay in time_range_bar.ZOOM_LIMIT_PRESETS.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from operator import attrgetter
from typing import Optional

from SciQLop.core.extensions import ExtensionPoint, declare, owned_by
from SciQLop.core.name_follower import CORE_OWNER


@dataclass(frozen=True)
class TimePreset:
    id: str  # what a user types in the palette, e.g. "1d"
    label: str  # what the bar shows
    seconds: float
    description: str = ""  # the palette's wording; "Last <label>" when empty


TIME_PRESETS = declare(ExtensionPoint("sciqlop.time_presets", TimePreset, what="time preset",
                                      doc="Time-range duration presets by id."))


def duration_presets() -> list[TimePreset]:
    return sorted(TIME_PRESETS.list(), key=attrgetter("seconds"))


def preset_seconds(text: str, default: float = 86400.0) -> float:
    seconds = parse_duration(text)
    return seconds if seconds is not None else default


_UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400, "w": 7 * 86400, "M": 30 * 86400, "y": 365.25 * 86400}
_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([mhdwMy])\s*$")


def parse_duration(text: str) -> Optional[float]:
    """Seconds for a preset id or label, or for a typed `<number><unit>` such as "1w", "90m" or "1.5h"
    (units m, h, d, w, M = 30 days, y); None when the text is neither."""
    preset = next((p for p in TIME_PRESETS.list() if text in (p.id, p.label)), None)
    if preset is not None:
        return preset.seconds
    match = _DURATION.match(text)
    if match is None or float(match.group(1)) == 0:
        return None
    return float(match.group(1)) * _UNIT_SECONDS[match.group(2)]


_CORE = (("1m", 60, "Last minute"), ("1h", 3600, "Last hour"), ("12h", 43200, "Last 12 hours"),
         ("1d", 86400, "Last day"), ("7d", 604800, "Last week"), ("1M", 30 * 86400, "Last month"))

with owned_by(CORE_OWNER):
    for _id, _seconds, _description in _CORE:
        TIME_PRESETS.contribute(TimePreset(_id, _id, _seconds, _description))

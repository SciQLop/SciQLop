"""The text an event's row shows in the event table, and the plain-text filter over it: what the
default event filter, and a provider's default filter_events, match. No Qt."""
from __future__ import annotations

from numbers import Real
from typing import Any


_SCI_LOWER = 1e-3
_SCI_UPPER = 1e6


def _format_float(value: float) -> str:
    """Format a float for display: scientific when very small or very large,
    general otherwise. Default precision is 6 significant digits."""
    if value == 0.0:
        return "0"
    abs_v = abs(value)
    if abs_v < _SCI_LOWER or abs_v >= _SCI_UPPER:
        return f"{value:.6e}"
    return f"{value:.6g}"


def _format_meta_value(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return str(value) if value is not None else ""
    if isinstance(value, Real) and not isinstance(value, int):
        return _format_float(float(value))
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, str):
        from datetime import datetime as _dt
        try:
            parsed = _dt.fromisoformat(value)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return str(value)


def format_event_time(dt) -> str:
    """To the second, and to the millisecond when it has any: two burst events in one second differ."""
    text = dt.strftime("%Y-%m-%d %H:%M:%S")
    return f"{text}.{dt.microsecond // 1000:03d}" if dt.microsecond >= 1000 else text


def event_text(event) -> str:
    """Its row as one lowercase text, a line per column, so a match never spans two cells."""
    cells = [format_event_time(event.start), format_event_time(event.stop),
             *(_format_meta_value(value) for value in event.meta.values())]
    return "\n".join(cells).lower()


def text_keeps(texts: list[tuple[str, str]], needle: str) -> set[str] | None:
    """The uuids whose text holds ``needle`` (any case); None when the needle is empty: all kept."""
    needle = needle.strip().lower()
    if not needle:
        return None
    return {uuid for uuid, text in texts if needle in text}

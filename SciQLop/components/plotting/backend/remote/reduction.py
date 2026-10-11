"""Reduce a data-source callback result to native-dtype numpy arrays.

`arity` is fixed by the graph type at INSTALL (2 = line/curve, 3 = colormap),
so we never guess shape from the data. A coloured channel receives one extra,
last array: the colour."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import List, Optional
import numpy as np


def epoch_seconds(time_values: np.ndarray) -> np.ndarray:
    arr = np.asarray(time_values)
    if np.issubdtype(arr.dtype, np.datetime64):
        return arr.astype("datetime64[ns]").astype("int64").astype(np.float64) / 1e9
    return np.ascontiguousarray(arr, dtype=np.float64)


def _is_speasy_variable(result) -> bool:
    try:
        from speasy.products.variable import SpeasyVariable
    except Exception:
        return False
    return isinstance(result, SpeasyVariable)


def _from_speasy(v, arity: int) -> List[np.ndarray]:
    x = epoch_seconds(v.time)
    if arity == 3:
        freq = np.ascontiguousarray(np.asarray(v.axes[1].values))
        z = np.ascontiguousarray(np.asarray(v.values))
        return [x, freq, z]
    y = np.ascontiguousarray(np.asarray(v.values))
    return [x, y]


def _from_sequence(seq, arity: int) -> List[np.ndarray]:
    if not isinstance(seq, (tuple, list)):
        raise TypeError(f"returned a {type(seq).__name__}; expected a tuple of {arity} arrays, "
                        "a SpeasyVariable or None")
    parts = list(seq)
    if len(parts) != arity:
        raise ValueError(f"expected {arity} arrays, got {len(parts)}")
    out = [epoch_seconds(parts[0])]
    out += [np.ascontiguousarray(np.asarray(p)) for p in parts[1:]]
    return out


def _colored_type():
    # Looked up, not imported: importing SciQLop.user_api pulls Qt into the worker,
    # and a Colored result means the callback already imported it.
    return getattr(sys.modules.get("SciQLop.user_api.data_types"), "Colored", None)


def reduce_result(result, arity: int) -> Optional[List[np.ndarray]]:
    """The arrays to ship, or None for "no data" (as None or Colored(None, ...))."""
    colored = _colored_type()
    if colored is not None and isinstance(result, colored):
        checked = result.checked()
        if checked.data is None:
            return None
        return reduce_result(checked.data, arity) + [checked.color]
    if _is_speasy_variable(result):
        return _from_speasy(result, arity)
    return _from_sequence(result, arity)


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def ensure_overlaps_request(t: np.ndarray, start: float, stop: float) -> None:
    """Data entirely outside the requested range draws nothing; usually the
    times are not epoch seconds (milliseconds land in the far future).
    *t* is in epoch seconds."""
    if len(t) and not np.any((t >= start) & (t <= stop)):
        raise ValueError(
            f"returned {len(t)} samples, none inside the requested range {_iso(start)} .. {_iso(stop)}. "
            "Times must be seconds since 1970-01-01 UTC, or datetime64")

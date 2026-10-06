"""Text report printed by `%%vp --debug`.

The debug panel shows its findings in an overlay, visible only on screen.
Notebook users read the cell output, and agents driving SciQLop only ever see
text, so the same facts are printed: what went in, what came out, and what the
checks found.
"""
import traceback
from typing import Any, Iterable, Mapping, Optional

import numpy as np
from speasy.products import SpeasyVariable

from SciQLop.user_api.virtual_products.validation import (
    Diagnostic, _filter_traceback, _fmt_duration, _fmt_epoch,
)

_MAX_COLUMNS = 5


def debug_report(name: str, start: float, stop: float, inputs: Mapping[str, Any], *,
                 data: Any = None, diagnostics: Iterable[Diagnostic] = (),
                 error: Optional[BaseException] = None, elapsed: float = 0.0) -> str:
    lines = [f"%%vp --debug: {name} over {_fmt_epoch(start)} -> {_fmt_epoch(stop)} "
             f"({_fmt_duration(stop - start)}), ran in {_fmt_duration(elapsed)}"]
    if inputs:
        lines += ["inputs:"] + [f"  {arg}: {describe(value)}" for arg, value in inputs.items()]
    if error is not None:
        return "\n".join(lines + [f"error: {type(error).__name__}: {error}", _traceback_of(error)])
    lines.append(f"result: {describe(data)}")
    diagnostics = list(diagnostics)
    lines += [f"{d.level}: {d.message}" for d in diagnostics] or ["checks: ok"]
    return "\n".join(lines)


def describe(value: Any) -> str:
    """One line on a VP input or result: shape, unit, labels, NaN share, values, time span."""
    from SciQLop.user_api.data_types import Colored
    if value is None:
        return "None (no data)"
    if isinstance(value, Colored):
        return f"{describe(value.data)}, coloured"
    if isinstance(value, SpeasyVariable):
        return _describe_variable(value)
    if isinstance(value, (tuple, list)) and len(value) >= 2 and hasattr(value[1], "shape"):
        return _describe_pair(np.asarray(value[0]), np.asarray(value[1]))
    return f"{type(value).__name__} {repr(value)[:80]}"


def _describe_variable(v: SpeasyVariable) -> str:
    columns = ", ".join(map(str, v.columns[:_MAX_COLUMNS])) + (", ..." if len(v.columns) > _MAX_COLUMNS else "")
    unit = f" {v.unit}" if v.unit else ""
    return (f"SpeasyVariable {v.values.shape}{unit} [{columns}], {_value_summary(v.values)}"
            f"{_time_span(v.time)}")


def _describe_pair(x: np.ndarray, y: np.ndarray) -> str:
    return f"(x, values) {y.shape}, {_value_summary(y)}{_time_span(x)}"


def _value_summary(values: np.ndarray) -> str:
    if values.size == 0:
        return "empty"
    if not np.issubdtype(values.dtype, np.number):
        return f"dtype {values.dtype}"
    nan_share = float(np.isnan(values).mean()) if np.issubdtype(values.dtype, np.floating) else 0.0
    if nan_share == 1.0:
        return "all NaN"
    stats = (f"min {np.nanmin(values):.4g} / median {np.nanmedian(values):.4g} / "
             f"max {np.nanmax(values):.4g}")
    return f"NaN {nan_share:.0%}, {stats}"


def _time_span(times: np.ndarray) -> str:
    if len(times) == 0:
        return ""
    if np.issubdtype(times.dtype, np.datetime64):
        first, last = (times[[0, -1]].astype("datetime64[ns]").astype(np.int64) / 1e9)
    elif np.issubdtype(times.dtype, np.number):
        first, last = float(times[0]), float(times[-1])
    else:
        return ""
    return f", {_fmt_epoch(first)} -> {_fmt_epoch(last)}"


def _traceback_of(error: BaseException) -> str:
    return _filter_traceback("".join(traceback.format_exception(error)))

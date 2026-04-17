# SciQLop/user_api/virtual_products/validation.py
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

import numpy as np
from speasy.products import SpeasyVariable


@dataclass
class Diagnostic:
    level: str  # "error", "warning", "info"
    message: str


@dataclass
class ValidationResult:
    data: Any
    diagnostics: List[Diagnostic] = field(default_factory=list)
    elapsed: float = 0.0


_EXPECTED_COMPONENTS = {
    "scalar": 1,
    "vector": 3,
}

# ensure_dt64 in easy_provider.py only handles these two dtypes
_ACCEPTED_TIME_DTYPES = {np.dtype("float64"), np.dtype("datetime64[ns]")}


def _filter_traceback(tb_text: str) -> str:
    """Keep only frames from user code, not SciQLop internals."""
    lines = tb_text.strip().split("\n")
    filtered = []
    skip = False
    for line in lines:
        if 'File "' in line and "SciQLop/" in line:
            skip = True
        else:
            if line.startswith("  ") and skip:
                continue
            skip = False
        if not skip:
            filtered.append(line)
    if filtered and filtered[-1] != lines[-1]:
        filtered.append(lines[-1])
    return "\n".join(filtered) if filtered else tb_text


# ---------------------------------------------------------------------------
# Individual checks — each returns List[Diagnostic]
# ---------------------------------------------------------------------------

def _check_return_type(data, declared_type: str) -> List[Diagnostic]:
    if isinstance(data, SpeasyVariable):
        return []
    if isinstance(data, (tuple, list)):
        if declared_type == "spectrogram":
            if len(data) < 3:
                return [Diagnostic("error",
                    f"Spectrogram requires (x, y, z) tuple, got {len(data)}-element {type(data).__name__}")]
        elif len(data) < 2:
            return [Diagnostic("error",
                f"Expected (x, y) tuple, got {len(data)}-element {type(data).__name__}")]
        return []
    return [Diagnostic("error",
        f"Expected SpeasyVariable or (x, y) tuple, got {type(data).__name__}. "
        f"This will silently become None in the plot pipeline")]


def _check_empty_data(data) -> List[Diagnostic]:
    if isinstance(data, SpeasyVariable):
        if data.values.size == 0:
            return [Diagnostic("warning", "Callback returned an empty SpeasyVariable (0 data points)")]
        return []
    if isinstance(data, (tuple, list)) and len(data) >= 2:
        x, y = data[0], data[1]
        if isinstance(x, np.ndarray) and x.size == 0:
            return [Diagnostic("warning", "Callback returned empty arrays (0 data points)")]
    return []


def _check_time_values_length(data, declared_type: str) -> List[Diagnostic]:
    if isinstance(data, SpeasyVariable):
        return []
    if not isinstance(data, (tuple, list)) or len(data) < 2:
        return []
    x, y = data[0], data[1]
    if not isinstance(x, np.ndarray) or not isinstance(y, np.ndarray):
        return []
    if x.size == 0:
        return []
    # For spectrograms, y is the spectral axis — length mismatch with x is expected
    if declared_type != "spectrogram" and len(x) != len(y):
        return [Diagnostic("error",
            f"Time vector length ({len(x)}) != values length ({len(y)}) — will crash in the plot layer")]
    return []


def _check_time_dtype(data) -> List[Diagnostic]:
    if isinstance(data, SpeasyVariable):
        return []
    if not isinstance(data, (tuple, list)) or len(data) < 2:
        return []
    x = data[0]
    if not isinstance(x, np.ndarray) or x.size == 0:
        return []
    if x.dtype not in _ACCEPTED_TIME_DTYPES:
        return [Diagnostic("warning",
            f"Time vector dtype is {x.dtype} — only float64 and datetime64[ns] "
            f"are accepted, this will raise ValueError at plot time")]
    return []


def _check_time_nans(data) -> List[Diagnostic]:
    t = _extract_time_vector(data)
    if t is None or t.size == 0:
        return []
    if np.any(np.isnan(t)):
        n = int(np.sum(np.isnan(t)))
        return [Diagnostic("error", f"Time vector contains {n} NaN value(s) — breaks plot axes")]
    if np.any(np.isinf(t)):
        n = int(np.sum(np.isinf(t)))
        return [Diagnostic("error", f"Time vector contains {n} Inf value(s) — breaks plot axes")]
    return []


def _check_shape(data, declared_type: str, labels: Optional[List[str]]) -> List[Diagnostic]:
    if isinstance(data, SpeasyVariable):
        return []
    if not isinstance(data, (tuple, list)) or len(data) < 2:
        return []

    y = data[1]
    if not isinstance(y, np.ndarray):
        return []

    expected = _EXPECTED_COMPONENTS.get(declared_type)
    if expected is None and labels:
        expected = len(labels)

    if expected and y.ndim == 2 and y.shape[1] != expected:
        return [Diagnostic("error",
            f"Declared {declared_type} ({expected} components) but got shape {y.shape}")]
    if expected and y.ndim == 1 and expected > 1:
        return [Diagnostic("error",
            f"Declared {declared_type} ({expected} components) but got shape {y.shape}")]
    return []


def _check_spectrogram_shape(data, declared_type: str) -> List[Diagnostic]:
    if declared_type != "spectrogram":
        return []
    if isinstance(data, SpeasyVariable):
        return []
    if not isinstance(data, (tuple, list)) or len(data) < 3:
        return []
    x, y, z = data[0], data[1], data[2]
    diagnostics = []
    if isinstance(z, np.ndarray):
        if z.ndim != 2:
            diagnostics.append(Diagnostic("error",
                f"Spectrogram z-array must be 2D, got {z.ndim}D shape {z.shape}"))
        elif isinstance(x, np.ndarray) and isinstance(y, np.ndarray):
            if z.shape != (len(x), len(y)):
                diagnostics.append(Diagnostic("error",
                    f"Spectrogram z shape {z.shape} doesn't match (len(x), len(y)) = ({len(x)}, {len(y)})"))
    return diagnostics


def _check_value_dtype(data) -> List[Diagnostic]:
    if isinstance(data, SpeasyVariable):
        return []
    if isinstance(data, (tuple, list)) and len(data) >= 2:
        y = data[1]
        if isinstance(y, np.ndarray) and y.dtype == np.float32:
            return [Diagnostic("warning", "Value array is float32 — intentional or precision loss?")]
    return []


def _check_execution_time(elapsed: float, start: Optional[float], stop: Optional[float]) -> List[Diagnostic]:
    if elapsed <= 0:
        return []
    diagnostics = []
    if start is not None and stop is not None:
        req_duration = stop - start
        ratio = elapsed / req_duration if req_duration > 0 else 0
        if ratio > 0.1:
            diagnostics.append(Diagnostic("warning",
                f"Callback took {_fmt_duration(elapsed)} for a {_fmt_duration(req_duration)} range "
                f"— every pan/zoom will re-invoke this"))
    elif elapsed > 5.0:
        diagnostics.append(Diagnostic("warning",
            f"Callback took {_fmt_duration(elapsed)} — every pan/zoom will re-invoke this"))
    return diagnostics


# ---------------------------------------------------------------------------
# Time extraction helpers
# ---------------------------------------------------------------------------

def _extract_time_vector(data) -> Optional[np.ndarray]:
    """Extract the time vector as epoch seconds from callback return data."""
    if isinstance(data, SpeasyVariable):
        t = data.time
        if isinstance(t, np.ndarray) and t.size > 0:
            if np.issubdtype(t.dtype, np.datetime64):
                return t.astype("datetime64[ns]").astype(np.float64) / 1e9
            return t.astype(np.float64)
        return None
    if isinstance(data, (tuple, list)) and len(data) >= 2:
        t = data[0]
        if isinstance(t, np.ndarray) and t.size > 0:
            if np.issubdtype(t.dtype, np.datetime64):
                return t.astype("datetime64[ns]").astype(np.float64) / 1e9
            return t.astype(np.float64)
    return None


def _check_time_coverage(data, start: Optional[float], stop: Optional[float]) -> List[Diagnostic]:
    if start is None or stop is None:
        return []

    t = _extract_time_vector(data)
    if t is None or t.size == 0:
        return []

    diagnostics = []
    if not np.all(np.diff(t) >= 0):
        diagnostics.append(Diagnostic("warning", "Time vector is not monotonically increasing"))

    t_min, t_max = float(t[0]), float(t[-1])
    req_duration = stop - start

    if t_max < start or t_min > stop:
        diagnostics.append(Diagnostic("error",
            f"Time vector [{_fmt_epoch(t_min)} .. {_fmt_epoch(t_max)}] "
            f"is entirely outside requested range [{_fmt_epoch(start)} .. {_fmt_epoch(stop)}]"))
        return diagnostics

    if t_min > start:
        gap = t_min - start
        pct = gap / req_duration * 100
        if pct > 5:
            diagnostics.append(Diagnostic("warning",
                f"Time vector starts {_fmt_duration(gap)} ({pct:.0f}%) after requested start"))

    if t_max < stop:
        gap = stop - t_max
        pct = gap / req_duration * 100
        if pct > 5:
            diagnostics.append(Diagnostic("warning",
                f"Time vector ends {_fmt_duration(gap)} ({pct:.0f}%) before requested stop"))

    return diagnostics


def _check_contiguity(data) -> Tuple[Any, List[Diagnostic]]:
    if isinstance(data, SpeasyVariable) or not isinstance(data, (tuple, list)):
        return data, []

    converted = list(data)
    for i, arr in enumerate(converted):
        if isinstance(arr, np.ndarray) and not arr.flags.c_contiguous:
            converted[i] = np.ascontiguousarray(arr)
    return tuple(converted), []


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_epoch(epoch: float) -> str:
    try:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    except (OSError, ValueError):
        return f"{epoch:.1f}s"


def _fmt_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}min"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_and_call(callback, start: float, stop: float,
                      declared_type: str, labels: Optional[List[str]]) -> ValidationResult:
    t0 = time.monotonic()
    try:
        data = callback(start, stop)
    except Exception:
        elapsed = time.monotonic() - t0
        tb = _filter_traceback(traceback.format_exc())
        return ValidationResult(
            data=None,
            diagnostics=[Diagnostic("error", tb)],
            elapsed=elapsed,
        )

    elapsed = time.monotonic() - t0
    return validate_with_data(data, declared_type, labels, elapsed, start=start, stop=stop)


def validate_with_data(data, declared_type: str, labels: Optional[List[str]],
                       elapsed: float = 0.0, *,
                       start: Optional[float] = None,
                       stop: Optional[float] = None) -> ValidationResult:
    """Validate pre-computed data without re-calling the callback."""
    if data is None:
        return ValidationResult(
            data=None,
            diagnostics=[Diagnostic("warning", "No data returned")],
            elapsed=elapsed,
        )

    diagnostics: List[Diagnostic] = []

    # Structural checks — bail on first error
    for check in [
        lambda: _check_return_type(data, declared_type),
        lambda: _check_empty_data(data),
        lambda: _check_time_values_length(data, declared_type),
        lambda: _check_shape(data, declared_type, labels),
        lambda: _check_spectrogram_shape(data, declared_type),
    ]:
        diags = check()
        diagnostics.extend(diags)
        if any(d.level == "error" for d in diags):
            return ValidationResult(data=None, diagnostics=diagnostics, elapsed=elapsed)
    data, contiguity_diags = _check_contiguity(data)
    diagnostics.extend(contiguity_diags)
    diagnostics.extend(_check_time_dtype(data))
    diagnostics.extend(_check_time_nans(data))
    diagnostics.extend(_check_time_coverage(data, start, stop))
    diagnostics.extend(_check_value_dtype(data))
    diagnostics.extend(_check_execution_time(elapsed, start, stop))

    return ValidationResult(data=data, diagnostics=diagnostics, elapsed=elapsed)

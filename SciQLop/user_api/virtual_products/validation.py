# SciQLop/user_api/virtual_products/validation.py
import time
import traceback
from dataclasses import dataclass, field
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
    # Always include the last line (the exception itself)
    if filtered and filtered[-1] != lines[-1]:
        filtered.append(lines[-1])
    return "\n".join(filtered) if filtered else tb_text


def _check_shape(data, declared_type: str, labels: Optional[List[str]]) -> List[Diagnostic]:
    if isinstance(data, SpeasyVariable):
        return []
    if not isinstance(data, (tuple, list)) or len(data) < 2:
        return [Diagnostic("error", f"Expected (x, y) tuple, got {type(data).__name__}")]

    y = data[1]
    if not isinstance(y, np.ndarray):
        return []

    diagnostics = []
    expected = _EXPECTED_COMPONENTS.get(declared_type)
    if expected is None and labels:
        expected = len(labels)

    if expected and y.ndim == 2 and y.shape[1] != expected:
        diagnostics.append(Diagnostic(
            "error",
            f"Declared {declared_type} ({expected} components) but got shape {y.shape}"
        ))
    elif expected and y.ndim == 1 and expected > 1:
        diagnostics.append(Diagnostic(
            "error",
            f"Declared {declared_type} ({expected} components) but got shape {y.shape}"
        ))

    return diagnostics


def _check_contiguity(data) -> Tuple[Any, List[Diagnostic]]:
    if isinstance(data, SpeasyVariable) or not isinstance(data, (tuple, list)):
        return data, []

    converted = list(data)
    for i, arr in enumerate(converted):
        if isinstance(arr, np.ndarray) and not arr.flags.c_contiguous:
            converted[i] = np.ascontiguousarray(arr)
    return tuple(converted), []


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
    return validate_with_data(data, declared_type, labels, elapsed)


def validate_with_data(data, declared_type: str, labels: Optional[List[str]],
                       elapsed: float = 0.0) -> ValidationResult:
    """Validate pre-computed data without re-calling the callback."""
    if data is None:
        return ValidationResult(
            data=None,
            diagnostics=[Diagnostic("warning", "No data returned")],
            elapsed=elapsed,
        )

    diagnostics = _check_shape(data, declared_type, labels)
    if any(d.level == "error" for d in diagnostics):
        return ValidationResult(data=None, diagnostics=diagnostics, elapsed=elapsed)

    data, contiguity_diags = _check_contiguity(data)
    diagnostics.extend(contiguity_diags)

    return ValidationResult(data=data, diagnostics=diagnostics, elapsed=elapsed)

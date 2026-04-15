"""Flatten a SpeasyVariable's direct attributes into an ISTP-style meta dict.

Pure-Python helper — no Qt, no SciQLopPlots, no speasy import at module load
time (the `variable` argument is duck-typed). Lets providers like AMDA that
don't populate the full ISTP attribute set still produce labeled plots, by
using `variable.name`, `variable.unit`, `variable.columns`, `variable.axes[i]`
as fallbacks. Existing meta entries always win — this never overwrites
upstream keys.
"""
from __future__ import annotations

import math
from typing import Any, Dict


def _first_scalar(value: Any) -> Any:
    while hasattr(value, "__len__") and not isinstance(value, str):
        try:
            if len(value) == 0:
                return None
            value = value[0]
        except (TypeError, IndexError):
            return None
    return value


def _is_nan(value: Any) -> bool:
    try:
        return isinstance(value, float) and math.isnan(value)
    except TypeError:
        return False


def _axis_as_istp_meta(axis) -> Dict[str, Any]:
    meta = dict(axis.meta) if axis.meta else {}
    if axis.unit:
        meta.setdefault("UNITS", axis.unit)
    if axis.name:
        meta.setdefault("LABLAXIS", axis.name)
    return meta


def variable_as_istp_meta(variable) -> Dict[str, Any]:
    meta: Dict[str, Any] = dict(variable.meta or {})
    if variable.unit:
        meta.setdefault("UNITS", variable.unit)
    if variable.name:
        meta.setdefault("LABLAXIS", variable.name)
        meta.setdefault("FIELDNAM", variable.name)
    if variable.columns:
        meta.setdefault("LABL_PTR_1", list(variable.columns))
    vr = getattr(variable, "valid_range", None)
    if vr is not None:
        try:
            vmin, vmax = vr
            vmin = _first_scalar(vmin)
            vmax = _first_scalar(vmax)
            if vmin is not None:
                meta.setdefault("VALIDMIN", vmin)
            if vmax is not None:
                meta.setdefault("VALIDMAX", vmax)
        except (TypeError, ValueError):
            pass
    fv = _first_scalar(getattr(variable, "fill_value", None))
    if fv is not None and not _is_nan(fv):
        meta.setdefault("FILLVAL", fv)
    if len(variable.axes) > 1:
        meta["_depend_1"] = _axis_as_istp_meta(variable.axes[1])
    return meta

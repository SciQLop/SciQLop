"""ISTP metadata → PlotHints translation.

Pure function shared by any provider whose upstream metadata follows the
ISTP/CDF convention (speasy inventory indexes, cdf_workbench variable info,
HAPI servers that re-publish CDAWeb data, ...).

No Qt dependency — fully unit-testable.
"""
from __future__ import annotations

import ast
from typing import Any, Iterable, Mapping, Optional

from SciQLop.core.plot_hints import AxisHints, PlotHints


def _first(value: Any) -> Any:
    """Return the first scalar of a list/tuple attribute, or the value itself."""
    while isinstance(value, (list, tuple)) and len(value) > 0:
        value = value[0]
    return value


def _as_str(value: Any) -> Optional[str]:
    value = _first(value)
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _as_float(value: Any) -> Optional[float]:
    value = _first(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scale(value: Any) -> Optional[str]:
    s = _as_str(value)
    if s is None:
        return None
    s = s.lower()
    if s.startswith("log"):
        return "log"
    if s.startswith("lin"):
        return "linear"
    return None


def _display_type(value: Any) -> Optional[str]:
    s = _as_str(value)
    if s is None:
        return None
    s = s.lower().strip()
    if s.startswith("spectrogram"):
        return "spectrogram"
    if s in ("time_series", "timeseries", "time series", "line", "plot"):
        return "line"
    return None


def _component_labels(meta: Mapping[str, Any]) -> Optional[list[str]]:
    raw = meta.get("LABL_PTR_1")
    if raw is not None:
        if isinstance(raw, (list, tuple)) and len(raw) > 0:
            if len(raw) == 1 and isinstance(raw[0], str):
                return _parse_list_string(raw[0])
            return [str(v) for v in raw]
        if isinstance(raw, str):
            return _parse_list_string(raw)
    lablaxis = meta.get("LABLAXIS")
    if isinstance(lablaxis, (list, tuple)) and len(lablaxis) > 1:
        return [str(v) for v in lablaxis]
    if isinstance(lablaxis, str) and lablaxis.startswith("["):
        return _parse_list_string(lablaxis)
    return None


def _parse_list_string(s: str) -> list[str]:
    try:
        value = ast.literal_eval(s)
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value]
    except (ValueError, SyntaxError):
        pass
    stripped = s.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]
    return [part.strip() for part in stripped.split(",") if part.strip()]


def _primary_label(meta: Mapping[str, Any]) -> Optional[str]:
    lablaxis = meta.get("LABLAXIS")
    if isinstance(lablaxis, str) and not lablaxis.startswith("["):
        return lablaxis
    if isinstance(lablaxis, (list, tuple)) and len(lablaxis) == 1:
        return _as_str(lablaxis)
    return _as_str(meta.get("FIELDNAM"))


def _valid_range(meta: Mapping[str, Any]) -> Optional[tuple[float, float]]:
    vmin = _as_float(meta.get("VALIDMIN"))
    vmax = _as_float(meta.get("VALIDMAX"))
    if vmin is None or vmax is None:
        return None
    return (vmin, vmax)


def istp_metadata_to_hints(meta: Mapping[str, Any]) -> PlotHints:
    """Translate a flat ISTP attribute dict to a PlotHints object.

    The caller may attach a `_depend_1` sub-mapping holding the DEPEND_1
    variable's own ISTP attributes — when present, it populates the y2 axis
    hints (used by spectrogram plots for the energy/frequency axis).
    """
    if meta is None:
        return PlotHints()

    display = _display_type(meta.get("DISPLAY_TYPE"))
    is_spectrogram = display == "spectrogram"

    unit = _as_str(meta.get("UNITS"))
    scale = _scale(meta.get("SCALETYP"))
    label = _primary_label(meta)
    valid = _valid_range(meta)
    fill = _as_float(meta.get("FILLVAL"))

    main_axis = AxisHints(label=label, unit=unit, scale=scale, valid_range=valid)

    y = AxisHints()
    z = AxisHints()
    if is_spectrogram:
        z = main_axis
    else:
        y = main_axis

    y2 = AxisHints()
    dep1 = meta.get("_depend_1")
    if isinstance(dep1, Mapping):
        y2 = AxisHints(
            label=_primary_label(dep1),
            unit=_as_str(dep1.get("UNITS")),
            scale=_scale(dep1.get("SCALETYP")),
            valid_range=_valid_range(dep1),
        )

    return PlotHints(
        display_type=display,
        y=y,
        y2=y2,
        z=z,
        component_labels=_component_labels(meta),
        fill_value=fill,
    )

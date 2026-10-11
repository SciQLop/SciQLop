"""Declarative plot-configuration hints produced by providers from their own metadata.

`PlotHints` is the single cross-provider vocabulary for axis labels, units,
scales, valid ranges, fill values and component labels. Providers translate
their native metadata (ISTP, HAPI, ...) into this model; `apply_plot_hints`
consumes it at the plotting boundary and calls the SciQLopPlots axis setters.

Pure data — no Qt, no SciQLopPlots import at module load time.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AxisHints(BaseModel):
    label: Optional[str] = None
    unit: Optional[str] = None
    scale: Optional[Literal["linear", "log"]] = None
    valid_range: Optional[tuple[float, float]] = None

    def composed_label(self) -> Optional[str]:
        if self.label and self.unit:
            return f"{self.label} [{self.unit}]"
        return self.label or (f"[{self.unit}]" if self.unit else None)


class PlotHints(BaseModel):
    display_type: Optional[Literal["line", "spectrogram"]] = None
    x: AxisHints = Field(default_factory=AxisHints)
    y: AxisHints = Field(default_factory=AxisHints)
    y2: AxisHints = Field(default_factory=AxisHints)
    z: AxisHints = Field(default_factory=AxisHints)
    component_labels: Optional[list[str]] = None
    fill_value: Optional[float] = None


def _apply_axis(axis, hints: AxisHints, owned: dict) -> None:
    if axis is None:
        return
    scale = None if hints.scale is None else hints.scale == "log"
    _set_unless_user_changed(axis, owned, "label", hints.composed_label())
    _set_unless_user_changed(axis, owned, "log", scale)


def _set_unless_user_changed(axis, owned: dict, field: str, value) -> None:
    """*owned* remembers what the axis held when hints last wrote *field*, or
    when they first saw it; a different value now was set by someone else
    (user API, Inspector, L key), and theirs wins. The first sighting is
    recorded even with nothing to write: a scale that only arrives with the
    data must not mistake the user's choice for the starting state."""
    setter, getter = getattr(axis, f"set_{field}", None), getattr(axis, field, None)
    if setter is None:
        return
    if getter is not None and owned.setdefault(field, getter()) != getter():
        return
    if value is not None:
        setter(value)
        owned[field] = value


def _get_axis(plot: Any, name: str):
    getter = getattr(plot, name, None)
    if getter is None:
        return None
    try:
        return getter()
    except Exception:
        return None


def _axis_is_empty(a: AxisHints) -> bool:
    return a.label is None and a.unit is None and a.scale is None and a.valid_range is None


def _first_non_empty_axis(entries, attr: str) -> AxisHints:
    for h in entries:
        a = getattr(h, attr)
        if not _axis_is_empty(a):
            return a
    return AxisHints()


def combine_hints(entries: list[PlotHints]) -> PlotHints:
    """Merge hints from several products sharing one plot.

    For the y axis (line plots), each entry contributes its composed label —
    the final y label is the comma-joined list of unique per-product labels
    ("Bt [nT], |B| [nT]"). Scale and valid_range take the first non-None.
    For y2/z (spectrogram axes, one per plot in practice), the first entry
    with a non-empty axis wins.
    """
    if not entries:
        return PlotHints()

    y_labels: list[str] = []
    for h in entries:
        cl = h.y.composed_label()
        if cl and cl not in y_labels:
            y_labels.append(cl)
    y = AxisHints(
        label=", ".join(y_labels) if y_labels else None,
        scale=next((h.y.scale for h in entries if h.y.scale), None),
        valid_range=next((h.y.valid_range for h in entries if h.y.valid_range), None),
    )

    return PlotHints(
        display_type=next((h.display_type for h in entries if h.display_type), None),
        y=y,
        y2=_first_non_empty_axis(entries, "y2"),
        z=_first_non_empty_axis(entries, "z"),
        x=_first_non_empty_axis(entries, "x"),
    )


def _merge_axis(base: AxisHints, extra: AxisHints) -> AxisHints:
    return AxisHints(
        label=base.label or extra.label,
        unit=base.unit or extra.unit,
        scale=base.scale or extra.scale,
        valid_range=base.valid_range or extra.valid_range,
    )


def merge_hints(base: PlotHints, extra: PlotHints) -> PlotHints:
    """Fill fields in `base` from `extra` only where `base` is empty.

    Used to refine inventory-time hints with post-fetch hints derived from the
    actual data variable — post-fetch never overwrites a value the inventory
    already provided.
    """
    return PlotHints(
        display_type=base.display_type or extra.display_type,
        x=_merge_axis(base.x, extra.x),
        y=_merge_axis(base.y, extra.y),
        y2=_merge_axis(base.y2, extra.y2),
        z=_merge_axis(base.z, extra.z),
        component_labels=base.component_labels or extra.component_labels,
        fill_value=base.fill_value if base.fill_value is not None else extra.fill_value,
    )


def apply_plot_hints(plot: Any, hints: PlotHints, owned: Optional[dict] = None) -> None:
    """Apply a `PlotHints` object to a SciQLopPlot-like plot instance.

    Only writes fields that are set. Safe to call with an empty `PlotHints()`.
    Tolerates plots that don't expose a given axis (returns silently).
    Pass the same *owned* dict on every call for one plot: a label or scale
    changed since the previous call is then left alone.
    """
    if plot is None:
        return
    owned = {} if owned is None else owned
    for name in ("y", "y2", "z", "x"):
        _apply_axis(_get_axis(plot, f"{name}_axis"), getattr(hints, name), owned.setdefault(name, {}))

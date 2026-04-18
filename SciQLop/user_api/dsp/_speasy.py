"""Helpers to round-trip between SpeasyVariable and (x, y) numpy arrays.

These helpers are internal to ``SciQLop.user_api.dsp``.
"""
from __future__ import annotations
from typing import Optional, Tuple, List

import numpy as np

from speasy.products import SpeasyVariable, VariableTimeAxis, VariableAxis
from speasy.core import datetime64_to_epoch, epoch_to_datetime64
from speasy.core.data_containers import DataContainer


def unwrap(v: SpeasyVariable) -> Tuple[np.ndarray, np.ndarray]:
    """Extract (epoch_seconds, values) from a SpeasyVariable as float64 numpy arrays."""
    return datetime64_to_epoch(v.time), np.asarray(v.values)


def rewrap_time_series(template: SpeasyVariable, values: np.ndarray, *,
                       time_epoch: Optional[np.ndarray] = None,
                       name_suffix: str = "") -> SpeasyVariable:
    """Build a new SpeasyVariable preserving template's metadata and unit.

    Parameters
    ----------
    template : SpeasyVariable
        Source variable used for axis/metadata templating.
    values : np.ndarray
        New value array (shape may differ when resampling/filtering).
    time_epoch : np.ndarray or None
        New time axis as float64 epoch seconds. If None, the template's
        time axis is kept.
    name_suffix : str
        Appended to the template's name (e.g. ``"_filtfilt"``).
    """
    time = template.time if time_epoch is None else epoch_to_datetime64(time_epoch)
    time_axis = VariableTimeAxis(values=time)
    other_axes = list(template.axes[1:])
    data = DataContainer(values=values, meta=dict(template.meta),
                         name=template.name + name_suffix)
    return SpeasyVariable(
        axes=[time_axis] + other_axes,
        values=data,
        columns=template.columns,
    )


def rewrap_spectrogram(template: SpeasyVariable,
                       t: np.ndarray, f: np.ndarray, power: np.ndarray, *,
                       name_suffix: str = "_spectrogram",
                       power_units: str = "") -> SpeasyVariable:
    """Wrap a spectrogram segment as a 2D SpeasyVariable (time x frequency).

    Power may be returned as ``(n_freq, n_time)`` and is transposed so the
    first axis is time. When ``n_freq == n_time`` the orientation is
    ambiguous; callers must ensure power is already ``(n_time, n_freq)``
    in that case.

    ``power_units`` overrides the unit of the output values — spectrogram
    power has different units than the input signal (e.g. ``nT^2/Hz``),
    so the template's ``UNITS`` is not propagated.
    """
    time_axis = VariableTimeAxis(values=epoch_to_datetime64(t))
    freq_axis = VariableAxis(name="frequency", meta={"UNITS": "Hz"}, values=f)
    if power.shape[0] == f.shape[0] and power.shape[1] == t.shape[0]:
        power = power.T
    meta = dict(template.meta)
    meta["UNITS"] = power_units
    data = DataContainer(values=power, meta=meta,
                         name=template.name + name_suffix)
    return SpeasyVariable(
        axes=[time_axis, freq_axis],
        values=data,
    )


def slice_segments(v: SpeasyVariable, segs: List[Tuple[int, int]]) -> List[SpeasyVariable]:
    """Slice a SpeasyVariable along its time axis using ``[(start, end), ...]`` index ranges."""
    return [v[start:end] for start, end in segs]

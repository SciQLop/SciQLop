"""SciQLop DSP user API.

Public functions accept either numpy arrays or a SpeasyVariable. When given
a SpeasyVariable, the result is rewrapped as a new SpeasyVariable preserving
metadata; for arrays, the result mirrors ``SciQLopPlots.dsp``.

Functions whose semantics change the time axis (``fft``, ``spectrogram``,
``resample``) document their rewrap behavior in the per-function docstring.

All public functions are marked @experimental_api().
"""
from __future__ import annotations
from typing import Tuple, List, Union

import numpy as np
from speasy.products import SpeasyVariable

from .._annotations import experimental_api
from . import _arrays as arrays
from . import _speasy as _sp


__all__ = [
    'arrays',
    'fft', 'filtfilt', 'sosfiltfilt', 'fir_filter', 'iir_sos',
    'resample', 'interpolate_nan', 'rolling_mean', 'rolling_std',
    'spectrogram', 'reduce', 'reduce_axes', 'split_segments',
]


def _is_var(o) -> bool:
    return isinstance(o, SpeasyVariable)


# --- Same-axis transforms (filtfilt, sosfiltfilt, fir_filter, iir_sos,
#     interpolate_nan, rolling_mean, rolling_std)
#     Rewrap with template metadata + name suffix.

@experimental_api()
def filtfilt(data, coeffs: np.ndarray, *, gap_factor: float = 3.0, has_gaps: bool = True):
    """Zero-phase FIR filter (forward-backward). Equivalent to scipy.signal.filtfilt.

    Accepts a SpeasyVariable (returns a new SpeasyVariable suffixed ``_filtfilt``).
    For raw arrays, use ``SciQLop.user_api.dsp.arrays.filtfilt(x, y, coeffs, ...)``.
    """
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.filtfilt(x, y, coeffs, gap_factor=gap_factor, has_gaps=has_gaps)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_filtfilt')
    raise TypeError("filtfilt(data, coeffs, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.filtfilt(x, y, coeffs) for arrays.")


@experimental_api()
def sosfiltfilt(data, sos: np.ndarray, *, gap_factor: float = 3.0, has_gaps: bool = True):
    """Zero-phase IIR (SOS) filter. Equivalent to scipy.signal.sosfiltfilt."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.sosfiltfilt(x, y, sos, gap_factor=gap_factor, has_gaps=has_gaps)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_sosfiltfilt')
    raise TypeError("sosfiltfilt(data, sos, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.sosfiltfilt(x, y, sos) for arrays.")


@experimental_api()
def fir_filter(data, coeffs: np.ndarray, *, gap_factor: float = 3.0):
    """FIR filter per segment."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.fir_filter(x, y, coeffs, gap_factor=gap_factor)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_fir')
    raise TypeError("fir_filter(data, coeffs, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.fir_filter(x, y, coeffs) for arrays.")


@experimental_api()
def iir_sos(data, sos: np.ndarray, *, gap_factor: float = 3.0):
    """IIR (SOS) filter per segment."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.iir_sos(x, y, sos, gap_factor=gap_factor)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_iir')
    raise TypeError("iir_sos(data, sos, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.iir_sos(x, y, sos) for arrays.")


@experimental_api()
def interpolate_nan(data, *, max_consecutive: int = 1):
    """Linearly interpolate NaN runs of length up to ``max_consecutive``."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        y_out = arrays.interpolate_nan(x, y, max_consecutive=max_consecutive)
        return _sp.rewrap_time_series(data, y_out, name_suffix='_interp_nan')
    raise TypeError("interpolate_nan(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.interpolate_nan(x, y, ...) for arrays.")


@experimental_api()
def rolling_mean(data, window: int, *, gap_factor: float = 3.0):
    """Gap-aware rolling mean."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.rolling_mean(x, y, window, gap_factor=gap_factor)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_rmean')
    raise TypeError("rolling_mean(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.rolling_mean(x, y, w) for arrays.")


@experimental_api()
def rolling_std(data, window: int, *, gap_factor: float = 3.0):
    """Gap-aware rolling standard deviation."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.rolling_std(x, y, window, gap_factor=gap_factor)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_rstd')
    raise TypeError("rolling_std(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.rolling_std(x, y, w) for arrays.")


# --- New-axis transforms (resample, fft, spectrogram, split_segments)

@experimental_api()
def resample(data, *, target_dt: float = 0.0, gap_factor: float = 3.0):
    """Resample to a uniform grid with sample spacing ``target_dt`` (seconds)."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.resample(x, y, gap_factor=gap_factor, target_dt=target_dt)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_resample')
    raise TypeError("resample(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.resample(x, y) for arrays.")


@experimental_api()
def fft(data, *, gap_factor: float = 3.0, window: str = 'hann') -> List[Tuple[np.ndarray, np.ndarray]]:
    """Per-segment FFT.

    Returns
    -------
    list of (freqs, magnitude)
        One per detected segment. ``SpeasyVariable`` cannot represent a
        frequency-only sample (its first axis must be time), so the FFT
        path returns raw numpy tuples even for SpeasyVariable inputs.
        Use ``spectrogram`` if you need a time-resolved spectrum wrapped
        as a ``SpeasyVariable``.
    """
    if _is_var(data):
        x, y = _sp.unwrap(data)
        return arrays.fft(x, y, gap_factor=gap_factor, window=window)
    raise TypeError("fft(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.fft(x, y) for arrays.")


@experimental_api()
def spectrogram(data, *, col: int = 0, window_size: int = 256, overlap: int = 0,
                gap_factor: float = 3.0, window: str = 'hann') -> List[SpeasyVariable]:
    """Per-segment spectrogram.

    Returns
    -------
    list of SpeasyVariable
        One per detected segment, each 2D (time x frequency). Suitable as
        input to ColorMap / Histogram2D plot wrappers.
    """
    if _is_var(data):
        x, y = _sp.unwrap(data)
        segs = arrays.spectrogram(x, y, col=col, window_size=window_size,
                                  overlap=overlap, gap_factor=gap_factor, window=window)
        return [_sp.rewrap_spectrogram(data, t, f, p) for t, f, p in segs]
    raise TypeError("spectrogram(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.spectrogram(x, y) for arrays.")


@experimental_api()
def reduce(data, op: str, *, gap_factor: float = 3.0):
    """Reduce columns of multi-column y to 1. ``op`` selects the reduction (e.g. 'sum', 'mean', 'norm')."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.reduce(x, y, op, gap_factor=gap_factor)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix=f'_reduce_{op}')
    raise TypeError("reduce(data, op, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.reduce(x, y, op) for arrays.")


@experimental_api()
def reduce_axes(data, shape: Tuple[int, ...], axes: Tuple[int, ...], *,
                op: str = 'sum', has_gaps: bool = False):
    """Reduce arbitrary axes within each row of a multi-column SpeasyVariable."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.reduce_axes(x, y, shape, axes, op=op, has_gaps=has_gaps)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix=f'_reduce_axes_{op}')
    raise TypeError("reduce_axes(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.reduce_axes(x, y, ...) for arrays.")


@experimental_api()
def split_segments(data, *, gap_factor: float = 3.0):
    """Detect gaps and slice the SpeasyVariable into segments.

    For arrays, see ``SciQLop.user_api.dsp.arrays.split_segments`` which returns
    raw ``[(start, end), ...]`` index ranges.
    """
    if _is_var(data):
        x, y = _sp.unwrap(data)
        segs = arrays.split_segments(x, y, gap_factor=gap_factor)
        return _sp.slice_segments(data, segs)
    raise TypeError("split_segments(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.split_segments(x, y) for arrays.")

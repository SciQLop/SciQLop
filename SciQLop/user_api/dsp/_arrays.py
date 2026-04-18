"""Thin typed pass-through layer over SciQLopPlots.dsp.

This module is internal — public users should import from
``SciQLop.user_api.dsp`` (the SpeasyVariable-aware facade in __init__.py).
Functions here accept and return numpy arrays only.
"""
from __future__ import annotations
from typing import Tuple, List

import numpy as np

from SciQLopPlots import dsp as _dsp

__all__ = [
    'fft', 'filtfilt', 'sosfiltfilt', 'fir_filter', 'iir_sos',
    'resample', 'interpolate_nan', 'rolling_mean', 'rolling_std',
    'spectrogram', 'reduce', 'reduce_axes', 'split_segments',
]


def fft(x: np.ndarray, y: np.ndarray, *,
        gap_factor: float = 3.0, window: str = 'hann',
        has_gaps: bool = True) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Per-segment FFT. See ``SciQLopPlots.dsp.fft``.

    Returns
    -------
    list of (freqs, magnitude) per segment.
    """
    return _dsp.fft(x, y, gap_factor=gap_factor, window=window, has_gaps=has_gaps)


def filtfilt(x: np.ndarray, y: np.ndarray, coeffs: np.ndarray, *,
             gap_factor: float = 3.0, has_gaps: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """Zero-phase FIR filter (forward-backward). Equivalent to scipy.signal.filtfilt."""
    return _dsp.filtfilt(x, y, coeffs, gap_factor=gap_factor, has_gaps=has_gaps)


def sosfiltfilt(x: np.ndarray, y: np.ndarray, sos: np.ndarray, *,
                gap_factor: float = 3.0, has_gaps: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """Zero-phase IIR filter (forward-backward SOS). Equivalent to scipy.signal.sosfiltfilt."""
    return _dsp.sosfiltfilt(x, y, sos, gap_factor=gap_factor, has_gaps=has_gaps)


def fir_filter(x: np.ndarray, y: np.ndarray, coeffs: np.ndarray, *,
               gap_factor: float = 3.0, has_gaps: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """FIR filter per segment."""
    return _dsp.fir_filter(x, y, coeffs, gap_factor=gap_factor, has_gaps=has_gaps)


def iir_sos(x: np.ndarray, y: np.ndarray, sos: np.ndarray, *,
            gap_factor: float = 3.0, has_gaps: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """IIR filter per segment. ``sos`` is an (n_sections, 6) SOS matrix."""
    return _dsp.iir_sos(x, y, sos, gap_factor=gap_factor, has_gaps=has_gaps)


def resample(x: np.ndarray, y: np.ndarray, *,
             gap_factor: float = 3.0, target_dt: float = 0.0,
             has_gaps: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """Resample to uniform grid per segment."""
    return _dsp.resample(x, y, gap_factor=gap_factor, target_dt=target_dt, has_gaps=has_gaps)


def interpolate_nan(x: np.ndarray, y: np.ndarray, *,
                    max_consecutive: int = 1) -> np.ndarray:
    """Linearly interpolate isolated NaN runs (up to ``max_consecutive``).

    Returns the interpolated y only; the time axis x is unchanged.
    """
    return _dsp.interpolate_nan(x, y, max_consecutive=max_consecutive)


def rolling_mean(x: np.ndarray, y: np.ndarray, window: int, *,
                 gap_factor: float = 3.0, has_gaps: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """Gap-aware rolling mean."""
    return _dsp.rolling_mean(x, y, window, gap_factor=gap_factor, has_gaps=has_gaps)


def rolling_std(x: np.ndarray, y: np.ndarray, window: int, *,
                gap_factor: float = 3.0, has_gaps: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """Gap-aware rolling standard deviation."""
    return _dsp.rolling_std(x, y, window, gap_factor=gap_factor, has_gaps=has_gaps)


def spectrogram(x: np.ndarray, y: np.ndarray, *,
                col: int = 0, window_size: int = 256, overlap: int = 0,
                gap_factor: float = 3.0, window: str = 'hann',
                has_gaps: bool = True) -> List[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Per-segment spectrogram. Returns a list of ``(t, f, power)`` per segment."""
    return _dsp.spectrogram(x, y, col=col, window_size=window_size, overlap=overlap,
                            gap_factor=gap_factor, window=window, has_gaps=has_gaps)


def reduce(x: np.ndarray, y: np.ndarray, op: str, *,
           gap_factor: float = 3.0, has_gaps: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """Reduce columns of y to 1. ``op`` selects the reduction (e.g. 'sum', 'mean', 'norm')."""
    return _dsp.reduce(x, y, op, gap_factor=gap_factor, has_gaps=has_gaps)


def reduce_axes(x: np.ndarray, y: np.ndarray, shape: Tuple[int, ...], axes: Tuple[int, ...], *,
                op: str = 'sum', has_gaps: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """Reduce arbitrary axes of an n-dim row layout. ``shape`` decomposes ``n_cols``; ``axes`` selects axes to reduce."""
    return _dsp.reduce_axes(x, y, shape, axes, op=op, has_gaps=has_gaps)


def split_segments(x: np.ndarray, y: np.ndarray, *,
                   gap_factor: float = 3.0) -> List[Tuple[int, int]]:
    """Detect gaps and return ``[(start, end), ...]`` index ranges (half-open)."""
    return _dsp.split_segments(x, y, gap_factor=gap_factor)

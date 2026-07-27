"""Per-channel background estimation and removal for 2-D spectrograms.

Composes the ``SciQLopPlots.dsp`` percentile kernels; kept out of
``_arrays.py``, which is a thin pass-through layer.
"""
from __future__ import annotations
from datetime import timedelta
from typing import Optional, Union

import numpy as np

from SciQLopPlots import dsp as _dsp

__all__ = ['background_subtract', 'resolve_window']

Window = Union[None, int, timedelta, np.timedelta64]

_MODES = ('diff', 'ratio', 'db')


def resolve_window(x: np.ndarray, window: Window) -> Optional[int]:
    """Normalize `window` to a sample count.

    `None` stays `None` (constant background). An `int` is a sample count.
    A `timedelta` / `np.timedelta64` is a duration, converted with the median
    sample spacing — robust to the inter-file gaps these products carry.

    Dispatch is by type, not by value: a bare `float` is rejected because
    ``window=300`` and ``window=300.0`` meaning different things is a silent
    error at sub-second cadences, not a visible one.
    """
    if window is None:
        return None
    if isinstance(window, bool):
        raise TypeError("window must be an int (samples) or a timedelta/np.timedelta64 "
                        "(duration), got bool")
    # np.timedelta64 subclasses np.signedinteger, so it must be checked
    # before the plain-int branch or it would be misread as a sample count.
    if isinstance(window, np.timedelta64):
        seconds = float(window / np.timedelta64(1, 's'))
    elif isinstance(window, (int, np.integer)):
        return int(window)
    elif isinstance(window, timedelta):
        seconds = window.total_seconds()
    else:
        raise TypeError("window must be None, an int (samples), or a "
                        f"timedelta/np.timedelta64 (duration), got {type(window).__name__}")

    if x.size < 2:
        raise ValueError("a duration window needs at least 2 samples to infer the cadence")
    median_dt = float(np.median(np.diff(x)))
    if not np.isfinite(median_dt) or median_dt <= 0.0:
        raise ValueError(f"cannot infer a positive sample cadence from x (median dt={median_dt})")
    return int(max(1, min(x.size, round(seconds / median_dt))))


def _realign_to_input(x: np.ndarray, x_bg: np.ndarray, bg: np.ndarray) -> np.ndarray:
    """Drop the gap-separator rows the DSP pipeline inserts.

    Every gap-aware ``Stage<T>`` kernel reassembles its segments with one
    extra NaN row per gap, timestamped at the gap midpoint (see
    ``Pipeline.hpp``'s ``reassemble``). The background would then be longer
    than the data it has to line up with. Separator timestamps are midpoints
    and never occur in `x`, and segment timestamps are copied verbatim, so
    `x` is an exact subsequence of `x_bg` and a searchsorted lookup recovers
    the original rows.
    """
    if bg.shape[0] == x.shape[0]:
        return bg                                   # no gaps, nothing inserted
    return bg[np.searchsorted(x_bg, x)]


def _apply_mode(y: np.ndarray, bg: np.ndarray, mode: str) -> np.ndarray:
    if mode == 'diff':
        return y - bg
    # NaN rather than +-inf where the ratio is undefined: the colormap hides
    # NaN, whereas one inf destroys the colour scale for the whole plot.
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.where((y > 0) & (bg > 0), y / bg, np.nan)
        return ratio if mode == 'ratio' else 10.0 * np.log10(ratio)


def background_subtract(x: np.ndarray, y: np.ndarray, *,
                        q: float = 50.0, window: Window = None,
                        mode: str = 'diff', gap_factor: float = 3.0) -> np.ndarray:
    """Remove a per-channel background from a 2-D spectrogram.

    Parameters
    ----------
    x : np.ndarray
        Time axis, epoch seconds.
    y : np.ndarray
        Values, shape (n_time,) or (n_time, n_freq).
    q : float
        Percentile of the background estimator. 50 is the median (default);
        5-10 is the robust choice when bursts fill much of the window.
    window : None | int | timedelta | np.timedelta64
        `None` estimates one constant background per channel over the whole
        window. Otherwise a sliding background of that many samples, or of
        that duration.
    mode : {'diff', 'ratio', 'db'}
        `S - bg`, `S / bg`, or `10*log10(S / bg)`. `ratio` and `db` yield NaN
        wherever `S <= 0` or `bg <= 0`.
    gap_factor : float
        Gap threshold for the sliding background; ignored when `window` is None.

    Returns
    -------
    np.ndarray
        Same shape and dtype as `y`.
    """
    if mode not in _MODES:
        raise ValueError(f"mode must be one of {_MODES}, got {mode!r}")

    x = np.asarray(x)
    y = np.asarray(y)
    samples = resolve_window(x, window)

    if samples is None:
        bg = _dsp.column_percentile(y, q)          # shape (n_cols,), broadcasts over rows
    else:
        x_bg, bg = _dsp.rolling_percentile(x, y, samples, q=q,
                                           gap_factor=gap_factor, has_gaps=True)
        if y.ndim == 2 and bg.ndim == 1:
            bg = bg.reshape(-1, 1)                  # rolling_percentile drops a size-1 column axis
        bg = _realign_to_input(x, x_bg, bg)
    return _apply_mode(y, bg, mode)

"""Upstream solar wind for the Earth models: OMNI 1-min, already time-shifted to the bow shock nose."""
import functools

import numpy as np

PRESSURE = "cdaweb/OMNI_HRO_1MIN/Pressure"   # nPa
BZ_GSM = "cdaweb/OMNI_HRO_1MIN/BZ_GSM"       # nT
# Sample times further than this from valid OMNI data on either side get NaN, so their section is
# dropped: bridging a long gap would draw a boundary for solar wind nobody measured.
MAX_GAP_S = 600.0


def _fetch(product: str, start: float, stop: float):
    import speasy
    return speasy.get_data(product, *(np.datetime64(int(s * 1e9), "ns") for s in (start, stop)))


def _get(product: str, start: float, stop: float) -> tuple[np.ndarray, np.ndarray]:
    v = _fetch(product, start, stop)
    if v is None:
        raise ValueError(f"no OMNI data ({product}) in this time range")
    v = v.replace_fillval_by_nan()
    return v.time.astype("datetime64[ns]").astype("int64") / 1e9, v.values[:, 0].astype(float)


def _interpolate(t: np.ndarray, values: np.ndarray, times: np.ndarray) -> np.ndarray:
    keep = np.isfinite(values)
    t, values = t[keep], values[keep]
    if len(t) == 0:
        return np.full(times.shape, np.nan)
    ext = np.concatenate([[-np.inf], t, [np.inf]])
    i = np.searchsorted(ext, times)
    bracketed = (times - ext[i - 1] <= MAX_GAP_S) & (ext[i] - times <= MAX_GAP_S)
    return np.where(bracketed, np.interp(times, t, values), np.nan)


@functools.lru_cache(maxsize=32)
def _upstream(product: str, times_bytes: bytes) -> np.ndarray:
    times = np.frombuffer(times_bytes)
    t, values = _get(product, times.min() - MAX_GAP_S, times.max() + MAX_GAP_S)
    return _interpolate(t, values, times)


def upstream(product: str, times: np.ndarray) -> np.ndarray:
    """*product* at *times* (epoch seconds, any shape). Cached by the times themselves, because a
    boundary's radius() is called with the same times on every bisection step."""
    flat = np.ascontiguousarray(times, dtype=float).ravel()
    return _upstream(product, flat.tobytes()).reshape(np.shape(times))

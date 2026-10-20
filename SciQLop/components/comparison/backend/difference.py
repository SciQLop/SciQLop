"""Pure-numpy math behind the Difference view."""
from typing import Callable, Literal, get_args

import numpy as np

Operation = Literal["difference", "ratio", "log_ratio"]

ISTP_FILL_THRESHOLD = 1e30

_RELATIONS: dict[str, Callable[[np.ndarray, np.ndarray], np.ndarray]] = {
    "difference": lambda a, b: a - b,
    "ratio": lambda a, b: a / b,
    "log_ratio": lambda a, b: np.log10(a / b),
}


class ComparisonMismatch(ValueError):
    pass


def relate(a: np.ndarray, b: np.ndarray, op: Operation) -> np.ndarray:
    if op not in _RELATIONS:
        raise ValueError(f"unknown operation {op!r}, expected one of {', '.join(get_args(Operation))}")
    with np.errstate(all="ignore"):
        out = np.asarray(_RELATIONS[op](a, b), dtype=float)
    return np.where(np.isfinite(out), out, np.nan)


def mask_fill(values: np.ndarray, fill_value: float | None) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    is_fill = np.abs(values) > ISTP_FILL_THRESHOLD
    if fill_value is not None:
        is_fill |= values == fill_value
    return np.where(is_fill, np.nan, values)


def _nearest_indices(t_src: np.ndarray, t_dst: np.ndarray) -> np.ndarray:
    right = np.clip(np.searchsorted(t_src, t_dst), 1, max(len(t_src) - 1, 1))
    left = right - 1
    right = np.minimum(right, len(t_src) - 1)
    return np.where(t_dst - t_src[left] <= t_src[right] - t_dst, left, right)


def _resample_column(t_src: np.ndarray, column: np.ndarray, t_dst: np.ndarray, method: str) -> np.ndarray:
    if method == "nearest":
        return column[_nearest_indices(t_src, t_dst)]
    if method == "linear":
        return np.interp(t_dst, t_src, column)
    raise ValueError(f"unknown resampling method {method!r}, expected linear or nearest")


def resample(t_src, values, t_dst, method: str = "linear") -> np.ndarray:
    t_src, t_dst = np.asarray(t_src, dtype=float), np.asarray(t_dst, dtype=float)
    values = np.asarray(values, dtype=float)
    columns = values.reshape(len(values), -1) if len(t_src) else values.reshape(0, 1)
    if len(t_src) == 0:
        return np.full((len(t_dst),) + values.shape[1:], np.nan)
    out = np.stack([_resample_column(t_src, c, t_dst, method) for c in columns.T], axis=1)
    outside = (t_dst < t_src[0]) | (t_dst > t_src[-1])
    out[outside] = np.nan
    return out.reshape((len(t_dst),) + values.shape[1:])


def _column_count(values: np.ndarray) -> int:
    return 1 if values.ndim == 1 else values.shape[1]


def line_relation(a: list, b: list, op: Operation, method: str) -> list:
    (t_a, v_a), (t_b, v_b) = a, b
    n_a, n_b = _column_count(np.asarray(v_a)), _column_count(np.asarray(v_b))
    if n_a != n_b:
        raise ComparisonMismatch(f"different number of components: {n_a} vs {n_b}")
    v_a = np.asarray(v_a, dtype=float)
    return [t_a, relate(v_a, resample(t_b, v_b, t_a, method).reshape(v_a.shape), op)]


def _constant_bins(y: np.ndarray) -> np.ndarray | None:
    y = np.asarray(y, dtype=float)
    if y.ndim == 1:
        return y
    return y[0] if np.allclose(y, y[0]) else None


def _same_bins(y_a: np.ndarray, y_b: np.ndarray) -> bool:
    bins_a, bins_b = _constant_bins(y_a), _constant_bins(y_b)
    return (bins_a is not None and bins_b is not None
            and bins_a.shape == bins_b.shape and np.allclose(bins_a, bins_b))


def colormap_relation(a: list, b: list, op: Operation, method: str) -> list:
    (t_a, y_a, z_a), (t_b, y_b, z_b) = a, b
    if not _same_bins(y_a, y_b):
        # simplify: bins must match; upgrade: 2D interpolation on A's bins in log-y.
        raise ComparisonMismatch("different energy bins — not supported yet")
    return [t_a, y_a, relate(np.asarray(z_a, dtype=float), resample(t_b, z_b, t_a, method), op)]

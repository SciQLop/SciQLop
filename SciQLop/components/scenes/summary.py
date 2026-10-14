"""Summarise a boundary's sections over an interval, per pane, in the scene frame."""
from dataclasses import dataclass
from typing import Literal

import numpy as np

from .boundary import Plane
from .frames import rotation

PANES = ((0, 1), (1, 2), (2, 0))   # XY, YZ, ZX
N_ANGLES = 720
# A resampled angle whose valid neighbours on either side are more than this many section steps
# apart is a gap. Distance to the nearest neighbour alone would keep a hook past an open end.
_GAP = 3
_REDUCERS = {"median": np.nanmedian, "mean": np.nanmean}


def pane_basis(pane: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    i, j = PANES[pane]
    e = np.eye(3)
    return e[i], e[j], e[3 - i - j]


@dataclass(frozen=True)
class SectionSummary:
    angles: np.ndarray
    centre: np.ndarray
    low: np.ndarray
    high: np.ndarray
    origin: np.ndarray   # pane origin of the polar coordinates, scene frame (3,)
    pane: int

    def curve(self, which: Literal["centre", "low", "high"]) -> tuple[np.ndarray, np.ndarray]:
        e1, e2, _ = pane_basis(self.pane)
        r = getattr(self, which)
        closed = np.append(r, r[0])
        a = np.append(self.angles, self.angles[0] + 2 * np.pi)
        return self.origin @ e1 + closed * np.cos(a), self.origin @ e2 + closed * np.sin(a)


def _polar(section: np.ndarray, e1, e2, origin) -> tuple[np.ndarray, np.ndarray]:
    rel = section - origin
    return np.arctan2(rel @ e2, rel @ e1), np.hypot(rel @ e1, rel @ e2)


def _bracket_width(grid: np.ndarray, sorted_angles: np.ndarray) -> np.ndarray:
    """Circular width between the sorted_angles just before and just after each grid angle, all in [-π, π]."""
    ext = np.concatenate([sorted_angles[-1:] - 2 * np.pi, sorted_angles, sorted_angles[:1] + 2 * np.pi])
    i = np.searchsorted(ext, grid)
    return ext[i] - ext[i - 1]


def _resample(angles: np.ndarray, radii: np.ndarray, grid: np.ndarray) -> np.ndarray:
    keep = np.isfinite(radii)
    if keep.sum() < 2:
        return np.full(grid.shape, np.nan)
    order = np.argsort(angles[keep])
    a, r = angles[keep][order], radii[keep][order]
    out = np.interp(grid, a, r, period=2 * np.pi)
    step = 2 * np.pi / len(angles)
    return np.where(_bracket_width(grid, a) > _GAP * step, np.nan, out)


def _reduce(reducer, resampled: np.ndarray) -> np.ndarray:
    """Reduce per angle; an angle no section reaches stays NaN (and raises no all-NaN warning)."""
    out = np.full(resampled.shape[1], np.nan)
    reached = np.isfinite(resampled).any(axis=0)
    out[reached] = reducer(resampled[:, reached], axis=0)
    return out


def summarise(sections: np.ndarray, pane: int, origin: np.ndarray,
              how: Literal["median", "mean"]) -> SectionSummary:
    if how not in _REDUCERS:
        raise ValueError(f"how must be one of {list(_REDUCERS)}, got {how!r}")
    e1, e2, _ = pane_basis(pane)
    grid = np.linspace(-np.pi, np.pi, N_ANGLES, endpoint=False)
    resampled = np.stack([_resample(*_polar(s, e1, e2, origin), grid) for s in sections])
    return SectionSummary(grid, _reduce(_REDUCERS[how], resampled), _reduce(np.nanmin, resampled),
                          _reduce(np.nanmax, resampled), origin, pane)


def pane_summary(model, scene_frame: str, pane: int, start: float, stop: float,
                 how: Literal["median", "mean"]) -> SectionSummary:
    times = model.sample_times(start, stop)
    to_model = rotation(scene_frame, model.frame, times)
    _, _, normal = pane_basis(pane)
    planes = Plane(normal=to_model.apply(np.tile(normal, (len(times), 1))), offset=np.zeros(len(times)))
    sections = model.cross_section(planes, times)
    to_scene = to_model.inv().as_matrix()
    in_scene = np.einsum("nij,nmj->nmi", to_scene, sections)
    focus = to_model.inv()[len(times) // 2].apply(np.asarray(model.focus, dtype=float))
    # simplify: one polar origin for the whole interval, the focus at mid-interval. Exact when the
    # focus is the body centre or the model frame is the scene frame (true for every built-in).
    origin = focus - (focus @ normal) * normal
    return summarise(in_scene, pane, origin, how)

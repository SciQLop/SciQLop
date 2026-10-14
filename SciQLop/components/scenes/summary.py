"""Summarise a boundary's sections over an interval, per pane, in the scene frame."""
import warnings
from dataclasses import dataclass

import numpy as np

from .boundary import Plane
from .frames import rotation

PANES = ((0, 1), (1, 2), (2, 0))   # XY, YZ, ZX
N_ANGLES = 720
_GAP = 3  # a resampled angle farther than this many section steps from any valid point is a gap
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

    def curve(self, which: str) -> tuple[np.ndarray, np.ndarray]:
        e1, e2, _ = pane_basis(self.pane)
        r = getattr(self, which)
        closed = np.append(r, r[0])
        a = np.append(self.angles, self.angles[0] + 2 * np.pi)
        return self.origin @ e1 + closed * np.cos(a), self.origin @ e2 + closed * np.sin(a)


def _polar(section: np.ndarray, e1, e2, origin) -> tuple[np.ndarray, np.ndarray]:
    rel = section - origin
    return np.arctan2(rel @ e2, rel @ e1), np.hypot(rel @ e1, rel @ e2)


def _resample(angles: np.ndarray, radii: np.ndarray, grid: np.ndarray) -> np.ndarray:
    keep = np.isfinite(radii)
    if keep.sum() < 2:
        return np.full(grid.shape, np.nan)
    order = np.argsort(angles[keep])
    a, r = angles[keep][order], radii[keep][order]
    out = np.interp(grid, a, r, period=2 * np.pi)
    step = 2 * np.pi / len(angles)
    gap = np.abs(np.angle(np.exp(1j * (grid[:, None] - a[None, :])))).min(axis=1) > _GAP * step
    return np.where(gap, np.nan, out)


def summarise(sections: np.ndarray, pane: int, origin: np.ndarray, how: str) -> SectionSummary:
    e1, e2, _ = pane_basis(pane)
    grid = np.linspace(-np.pi, np.pi, N_ANGLES, endpoint=False)
    resampled = np.stack([_resample(*_polar(s, e1, e2, origin), grid) for s in sections])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN angles stay NaN
        return SectionSummary(grid, _REDUCERS[how](resampled, axis=0), np.nanmin(resampled, axis=0),
                              np.nanmax(resampled, axis=0), origin, pane)


def pane_summary(model, scene_frame: str, pane: int, start: float, stop: float, how: str) -> SectionSummary:
    times = model.sample_times(start, stop)
    to_model = rotation(scene_frame, model.frame, times)
    _, _, normal = pane_basis(pane)
    planes = Plane(normal=to_model.apply(np.tile(normal, (len(times), 1))), offset=np.zeros(len(times)))
    sections = model.cross_section(planes, times)
    to_scene = to_model.inv().as_matrix()
    in_scene = np.einsum("nij,nmj->nmi", to_scene, sections)
    focus = to_model.inv()[len(times) // 2].apply(np.asarray(model.focus, dtype=float))
    # simplify: one polar origin for the whole interval, the focus at mid-interval. Exact when the
    # model frame is the scene frame or the focus is the body centre (every built-in model).
    origin = focus - (focus @ normal) * normal
    return summarise(in_scene, pane, origin, how)

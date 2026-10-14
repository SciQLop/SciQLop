"""Boundaries star-shaped around a focus: r = r(θ, φ, t)."""
from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np

_BISECTIONS = 60
_FAR = 1e3  # body radii; a ray still inside the boundary this far out has no crossing


@dataclass(frozen=True)
class Plane:
    normal: np.ndarray   # (n, 3) unit normals, one per time
    offset: np.ndarray   # (n,) signed distance from the origin


class Boundary(Protocol):
    """What a scene needs from a boundary model. RadialBoundary implements it; a
    non-radial model implements sample_times and cross_section itself.

    Limitation: scenes summarise every section as if star-shaped around the origin, so a
    non-radial model with non-star-shaped sections is drawn with a wrong curve."""
    name: str
    body: str
    kind: str
    frame: str
    label: str
    description: str
    reference: str
    focus: tuple[float, float, float]

    def sample_times(self, start: float, stop: float) -> np.ndarray: ...

    def cross_section(self, planes: Plane, times: np.ndarray) -> np.ndarray: ...


def _in_plane_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    helper = np.where(np.abs(normal[:, :1]) < 0.9, [[1.0, 0, 0]], [[0, 1.0, 0]])
    u = np.cross(normal, helper)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    return u, np.cross(normal, u)


def _spherical(rel: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r = np.linalg.norm(rel, axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        theta = np.arccos(np.clip(rel[..., 0] / r, -1, 1))
    return r, theta, np.arctan2(rel[..., 2], rel[..., 1])


class RadialBoundary:
    name: str
    body: str
    kind: str
    frame: str
    label: str = ""
    description: str = ""
    reference: str = ""
    focus: tuple[float, float, float] = (0.0, 0.0, 0.0)
    theta_max: float = np.deg2rad(150)
    cadence: Optional[float] = None
    n_samples: int = 200
    n_rays: int = 720

    def radius(self, theta: np.ndarray, phi: np.ndarray, times: np.ndarray) -> np.ndarray:
        """Boundary distance from the focus, in body radii, shape (n, m) like theta and phi
        (n times, m rays). times (epoch seconds) is (n, 1), so it broadcasts against them."""
        raise NotImplementedError

    def sample_times(self, start: float, stop: float) -> np.ndarray:
        if self.cadence:
            return np.arange(start, stop + self.cadence / 2, self.cadence)
        return np.linspace(start, stop, self.n_samples)

    def _outside(self, points: np.ndarray, times: np.ndarray) -> np.ndarray:
        r, theta, phi = _spherical(points - np.asarray(self.focus))
        with np.errstate(invalid="ignore"):
            return (theta > self.theta_max) | (r > self.radius(theta, phi, times[:, None]))

    def cross_section(self, planes: Plane, times: np.ndarray) -> np.ndarray:
        """Bisection along rays from the focus projected onto each plane."""
        focus = np.asarray(self.focus, dtype=float)
        n = planes.normal
        centre = focus - ((n @ focus) - planes.offset)[:, None] * n           # (n, 3)
        u, v = _in_plane_basis(n)
        a = np.linspace(-np.pi, np.pi, self.n_rays, endpoint=False)
        rays = np.cos(a)[None, :, None] * u[:, None] + np.sin(a)[None, :, None] * v[:, None]   # (n, m, 3)

        def point(s: np.ndarray) -> np.ndarray:
            return centre[:, None] + s[..., None] * rays

        lo, hi = np.zeros(rays.shape[:2]), np.full(rays.shape[:2], _FAR)
        # simplify: radius() is re-evaluated on every bisection step although theta/phi are constant
        # along a ray when the plane contains the focus. Upgrade path: evaluate it once per ray then.
        for _ in range(_BISECTIONS):
            mid = (lo + hi) / 2
            out = self._outside(point(mid), times)
            hi, lo = np.where(out, mid, hi), np.where(out, lo, mid)
        crossing = point(hi)
        valid = ~self._outside(point(lo), times) & (hi < _FAR * 0.999)
        _, theta, _ = _spherical(crossing - focus)
        valid &= (theta < self.theta_max - 1e-6) | (self.theta_max >= np.pi)
        return np.where(valid[..., None], crossing, np.nan)

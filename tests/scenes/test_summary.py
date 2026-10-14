import warnings

import numpy as np
import pytest

from SciQLop.components.scenes import summary
from SciQLop.components.scenes.boundary import RadialBoundary
from SciQLop.components.scenes.summary import pane_basis, pane_summary, summarise


def circle(radius, n=360, phase=0.0, z=0.0):
    a = np.linspace(-np.pi, np.pi, n, endpoint=False) + phase
    return np.stack([radius * np.cos(a), radius * np.sin(a), np.full(n, z)], axis=1)


def test_pane_bases():
    e1, e2, n = pane_basis(1)
    assert np.allclose(e1, [0, 1, 0]) and np.allclose(e2, [0, 0, 1]) and np.allclose(n, [1, 0, 0])


def test_sections_sampled_at_different_angles_are_reduced_per_angle():
    sections = [circle(2.0, 360), circle(4.0, 500, phase=0.003)]
    s = summarise(sections, pane=0, origin=np.zeros(3), how="median")
    assert np.allclose(s.centre, 3.0, atol=1e-6)
    assert np.allclose(s.low, 2.0, atol=1e-6) and np.allclose(s.high, 4.0, atol=1e-6)


def test_mean_and_nan_are_handled():
    third = np.full((360, 3), np.nan)
    sections = np.stack([circle(2.0), circle(5.0), third])
    s = summarise(sections, pane=0, origin=np.zeros(3), how="mean")
    assert np.allclose(s.centre, 3.5, atol=1e-6)


def test_an_asymmetric_section_keeps_its_orientation():
    shifted = circle(2.0) + [0.5, 0, 0]          # still contains the origin, so star-shaped around it
    s = summarise(shifted[None], pane=0, origin=np.zeros(3), how="median")
    x, y = s.curve("centre")
    assert np.nanmax(x) == pytest.approx(2.5, abs=1e-3) and np.nanmin(x) == pytest.approx(-1.5, abs=1e-3)


def test_open_tail_leaves_a_gap():
    c = circle(3.0)
    c[np.abs(np.arctan2(c[:, 1], c[:, 0])) > np.deg2rad(150)] = np.nan
    s = summarise(c[None], pane=0, origin=np.zeros(3), how="median")
    tail = np.abs(s.angles) > np.deg2rad(155)
    assert np.all(np.isnan(s.centre[tail])) and np.all(np.isfinite(s.centre[np.abs(s.angles) < np.deg2rad(140)]))


class TiltedSphereInGSE(RadialBoundary):
    """A sphere at the origin, in another frame: rotating it must not change its section."""
    name, body, kind, frame = "tilted", "earth", "test", "GSE"
    n_samples = 3
    theta_max = np.pi

    def radius(self, theta, phi, times):
        return np.full(np.shape(theta), 2.0)


def _stub_rotation(monkeypatch, rotvec_per_time):
    from scipy.spatial.transform import Rotation
    monkeypatch.setattr(summary, "rotation",
                        lambda f, t, times: Rotation.from_rotvec(np.asarray(rotvec_per_time(len(times)))))


def test_rotation_happens_before_reduction(monkeypatch):
    angles = np.deg2rad([0.0, 10.0, 20.0])
    _stub_rotation(monkeypatch, lambda n: np.stack([angles[:n], 0 * angles[:n], 0 * angles[:n]], axis=1))
    s = pane_summary(TiltedSphereInGSE(), "GSM", pane=0, start=0.0, stop=2.0, how="median")
    assert np.allclose(s.centre, 2.0, atol=1e-6)   # a sphere at the origin is rotation-invariant
    assert s.origin.shape == (3,)


class OffsetBallInGSE(RadialBoundary):
    name, body, kind, frame = "ball", "earth", "test", "GSE"
    focus = (3.0, 0.0, 0.0)
    n_samples = 3
    theta_max = np.pi

    def radius(self, theta, phi, times):
        return np.ones(np.shape(theta))


def test_off_centre_boundary_lands_where_the_inverse_rotation_puts_it(monkeypatch):
    """scene->model is +90 deg about z, so model (3,0,0) is scene (0,-3,0)."""
    _stub_rotation(monkeypatch, lambda n: np.tile([0, 0, np.pi / 2], (n, 1)))
    s = pane_summary(OffsetBallInGSE(), "GSM", pane=0, start=0.0, stop=2.0, how="median")
    x, y = s.curve("centre")
    assert np.allclose(s.origin, [0, -3, 0], atol=1e-9)
    assert (x.min(), x.max()) == pytest.approx((-1.0, 1.0), abs=1e-3)
    assert (y.min(), y.max()) == pytest.approx((-4.0, -2.0), abs=1e-3)


def test_bad_reducer_names_the_allowed_ones():
    with pytest.raises(ValueError, match="median.*mean"):
        summarise(circle(1.0)[None], pane=0, origin=np.zeros(3), how="mode")


def test_angles_no_section_reaches_stay_nan_without_warnings():
    c = circle(3.0)
    c[np.abs(np.arctan2(c[:, 1], c[:, 0])) > np.deg2rad(150)] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for how in ("median", "mean"):
            s = summarise(np.stack([c, c]), pane=0, origin=np.zeros(3), how=how)
    assert np.isnan(s.low[np.abs(s.angles) > np.deg2rad(155)]).all()


def _brute_force_gap(grid, valid_angles, step):
    return np.abs(np.angle(np.exp(1j * (grid[:, None] - valid_angles[None, :])))).min(axis=1) > summary._GAP * step


@pytest.mark.parametrize("seed", range(5))
def test_gap_mask_matches_the_brute_force_circular_distance(seed):
    rng = np.random.default_rng(seed)
    angles = rng.uniform(-np.pi, np.pi, 300)
    radii = np.where(rng.uniform(size=300) < 0.3, np.nan, 2.0)
    radii[np.abs(angles - 1.0) < 0.4] = np.nan
    grid = np.linspace(-np.pi, np.pi, summary.N_ANGLES, endpoint=False)
    out = summary._resample(angles, radii, grid)
    expected = _brute_force_gap(grid, angles[np.isfinite(radii)], 2 * np.pi / len(angles))
    assert np.array_equal(np.isnan(out), expected)

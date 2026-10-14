import numpy as np
import pytest

from SciQLop.components.scenes.boundary import Plane, RadialBoundary


class Sphere(RadialBoundary):
    name, body, kind, frame = "sphere", "earth", "test", "GSM"
    theta_max = np.pi

    def radius(self, theta, phi, times):
        return np.full(np.shape(theta), 3.0)


class Conic(RadialBoundary):
    """r = L / (1 + e cos θ) from a focus on +X: an ellipse, closed on every ray."""
    name, body, kind, frame = "conic", "mars", "test", "MSO"
    focus = (0.6, 0.0, 0.0)
    theta_max = np.pi

    def radius(self, theta, phi, times):
        return 2.0 / (1 + 0.5 * np.cos(theta))


class Paraboloid(RadialBoundary):
    """Shue-like, open tail."""
    name, body, kind, frame = "open", "earth", "test", "GSM"

    def radius(self, theta, phi, times):
        return 10.0 * (2 / (1 + np.cos(theta))) ** 0.5


def planes(normal, n=1, offset=0.0):
    return Plane(normal=np.tile(normal, (n, 1)).astype(float), offset=np.full(n, offset))


@pytest.mark.parametrize("normal", [(0, 0, 1), (1, 0, 0), (0, 1, 0)])
def test_a_sphere_cuts_as_a_circle_in_every_pane(normal):
    s = Sphere().cross_section(planes(normal), np.array([0.0]))
    assert s.shape == (1, 720, 3)
    assert np.allclose(np.linalg.norm(s[0], axis=1), 3.0)
    assert np.allclose(s[0] @ np.array(normal, float), 0.0)


def test_a_conic_section_through_its_focus_matches_the_formula():
    s = Conic().cross_section(planes((0, 0, 1)), np.array([0.0]))[0]
    rel = s - np.array(Conic.focus)
    theta = np.arccos(rel[:, 0] / np.linalg.norm(rel, axis=1))
    assert np.allclose(np.linalg.norm(rel, axis=1), 2.0 / (1 + 0.5 * np.cos(theta)))


def test_a_pane_missing_the_focus_still_gets_the_true_boundary():
    s = Conic().cross_section(planes((1, 0, 0)), np.array([0.0]))[0]   # x = 0, focus at x = 0.6
    assert np.all(np.isfinite(s)) and np.allclose(s[:, 0], 0.0)
    rel = s - np.array(Conic.focus)
    theta = np.arccos(rel[:, 0] / np.linalg.norm(rel, axis=1))
    assert np.allclose(np.linalg.norm(rel, axis=1), 2.0 / (1 + 0.5 * np.cos(theta)), atol=1e-9)


def test_each_time_gets_its_own_plane():
    p = Plane(normal=np.array([[0, 0, 1.0], [1.0, 0, 0]]), offset=np.zeros(2))
    s = Sphere().cross_section(p, np.array([0.0, 1.0]))
    assert np.allclose(s[0, :, 2], 0) and np.allclose(s[1, :, 0], 0)


def test_rays_past_theta_max_are_nan():
    s = Paraboloid().cross_section(planes((0, 0, 1)), np.array([0.0]))[0]
    finite = np.isfinite(s[:, 0])
    assert finite.any() and not finite.all()
    theta = np.arccos(s[finite, 0] / np.linalg.norm(s[finite], axis=1))
    assert np.all(theta <= Paraboloid.theta_max)


def test_sample_times_follow_cadence_or_count():
    assert len(Sphere().sample_times(0.0, 100.0)) == 200
    cadenced = type("C", (Sphere,), {"cadence": 10.0})()
    assert np.allclose(cadenced.sample_times(0.0, 100.0), np.arange(0.0, 101.0, 10.0))

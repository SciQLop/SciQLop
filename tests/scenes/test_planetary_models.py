import numpy as np
import pytest

from SciQLop.components.scenes.boundary import Plane
from SciQLop.components.scenes.frames import frame_centres
from SciQLop.plugins.planetary_scenes import BODIES_DATA, SCENES_DATA
from SciQLop.plugins.planetary_scenes.models import (Jelinek2012BowShock, Shue1998, Vignes2000BowShock,
                                                     Vignes2000MPB, Winslow2013BowShock, Winslow2013Magnetopause)


def r_at(model, theta_deg):
    t = np.deg2rad(np.array([[theta_deg]]))
    return float(model.radius(t, np.zeros_like(t), np.zeros_like(t))[0, 0])


@pytest.mark.parametrize("model, theta, expected", [
    (Shue1998(), 0, 10.251873), (Shue1998(), 90, 15.427840),
    (Jelinek2012BowShock(), 0, 13.511736), (Jelinek2012BowShock(), 90, 23.096985),
    (Winslow2013Magnetopause(), 0, 1.45), (Winslow2013Magnetopause(), 90, 2.050610),
])
def test_radius_matches_reference(model, theta, expected):
    assert r_at(model, theta) == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize("model, subsolar_x", [
    (Vignes2000BowShock(), 1.644926), (Vignes2000MPB(), 1.285263), (Winslow2013BowShock(), 1.848039)])
def test_conic_subsolar_point(model, subsolar_x):
    focus_plane = Plane(normal=np.array([[0, 0, 1.0]]), offset=np.array([model.focus[2]]))
    s = model.cross_section(focus_plane, np.array([0.0]))[0]
    assert np.nanmax(s[:, 0]) == pytest.approx(subsolar_x, abs=1e-3)


def test_every_scene_frame_is_centred_on_its_body():
    bodies = {b.name: b for b in BODIES_DATA}
    for scene in SCENES_DATA:
        assert frame_centres()[scene.frame] == bodies[scene.body].threedview, scene.name


def test_every_model_is_labelled_and_cited():
    from SciQLop.plugins.planetary_scenes import MODELS
    for m in MODELS:
        assert m.label and m.reference.startswith("doi:") and m.frame in frame_centres()


def test_register_all_makes_the_scenes_resolvable(monkeypatch):
    from SciQLop.components.scenes import registry
    from SciQLop.components.scenes.model import resolve
    from SciQLop.plugins.planetary_scenes import register_all
    for reg in (registry.BODIES, registry.BOUNDARIES, registry.SCENES):
        monkeypatch.setattr(reg, "_items", {})
    register_all()
    for scene in SCENES_DATA:
        assert resolve(scene.name).boundaries

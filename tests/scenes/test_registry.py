import astropy.units as u
import numpy as np
import pytest

from SciQLop.components.scenes.boundary import RadialBoundary
from SciQLop.components.scenes.frames import FrameError
from SciQLop.components.scenes.model import Body, Scene, resolve
from SciQLop.components.scenes.registry import BODIES, BOUNDARIES, SCENES, NotRegistered, Registry


class Ball(RadialBoundary):
    name, body, kind, frame = "ball", "earth", "magnetopause", "GSM"

    def radius(self, theta, phi, times):
        return np.full(np.shape(theta), 10.0)


@pytest.fixture
def registries(monkeypatch):
    for reg in (BODIES, BOUNDARIES, SCENES):
        monkeypatch.setattr(reg, "_items", {})
    BODIES.register(Body("earth", 6371.2 * u.km, "Earth", "R_E"))
    BOUNDARIES.register(Ball())


def test_duplicates_raise_unless_replaced(registries):
    with pytest.raises(ValueError, match="boundary 'ball' is already registered"):
        BOUNDARIES.register(Ball())
    BOUNDARIES.register(Ball(), replace=True)


def test_list_filters_on_attributes(registries):
    assert [b.name for b in BOUNDARIES.list(body="earth", kind="magnetopause")] == ["ball"]
    assert BOUNDARIES.list(body="mars") == []


def test_names_resolve_late_and_missing_ones_list_what_exists(registries):
    scene = Scene("Earth", "earth", "GSM", {"magnetopause": "ball", "bow_shock": "later"})
    SCENES.register(scene)
    with pytest.raises(NotRegistered, match="no boundary named 'later'.*available: ball"):
        resolve("Earth")


def test_a_resolved_scene_holds_objects(registries):
    r = resolve(Scene("Earth", "earth", "GSM", {"magnetopause": "ball"}))
    assert r.body.symbol == "R_E" and isinstance(r.boundaries["magnetopause"], Ball)


def test_a_model_of_another_body_is_refused(registries):
    martian = type("M", (Ball,), {"name": "m", "body": "mars"})()
    with pytest.raises(ValueError, match="'m' is a mars model.*earth scene"):
        resolve(Scene("Earth", "earth", "GSM", {"magnetopause": martian}))


def test_a_scene_frame_must_be_centred_on_its_body(registries):
    with pytest.raises(FrameError, match="MSO is centred on Mars, not Earth"):
        resolve(Scene("Earth", "earth", "MSO", {}))


def test_a_lowercase_scene_frame_resolves_normalised(registries):
    assert resolve(Scene("Earth", "earth", "gsm", {})).scene.frame == "GSM"


def test_an_unknown_scene_frame_is_named_as_unknown(registries):
    with pytest.raises(FrameError, match="3DView does not know the frame 'nope'"):
        resolve(Scene("Earth", "earth", "nope", {}))


def test_with_boundary_swaps_one_kind(registries):
    s = Scene("Earth", "earth", "GSM", {"magnetopause": "ball"}).with_boundary("magnetopause", "other")
    assert s.boundaries == {"magnetopause": "other"}


def test_public_surface_reexports():
    from SciQLop.user_api import scenes
    for name in ("Body", "Scene", "Boundary", "RadialBoundary", "Plane", "register_body", "register_boundary",
                 "register_scene", "list_bodies", "list_boundaries", "list_scenes"):
        assert hasattr(scenes, name)

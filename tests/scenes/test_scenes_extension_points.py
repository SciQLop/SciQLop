"""Scenes are the first extension-point client: planetary_scenes contributes like a third party."""
from pathlib import Path

from SciQLop.core import extensions

from ..fixtures import *  # noqa: F401, F403


def test_scene_registries_are_declared_extension_points():
    from SciQLop.components.scenes.registry import BODIES, BOUNDARIES, SCENES
    assert extensions.get("sciqlop.scenes.bodies") is BODIES
    assert extensions.get("sciqlop.scenes.boundaries") is BOUNDARIES
    assert extensions.get("sciqlop.scenes.scenes") is SCENES


def test_planetary_scenes_contributions_are_owned_and_match_plugin_json(main_window, monkeypatch):
    from SciQLop.components.scenes import registry
    from SciQLop.components.plugins.backend.loader.context import PluginContext
    from SciQLop.components.plugins.testing import assert_provides_matches
    from SciQLop.plugins import planetary_scenes
    for reg in (registry.BODIES, registry.BOUNDARIES, registry.SCENES):
        monkeypatch.setattr(reg, "_items", {})
        monkeypatch.setattr(reg, "_owners", {})
    planetary_scenes.activate(PluginContext("planetary_scenes", "1.0.0", main_window, frozenset()))
    assert registry.SCENES.owner_of("Earth environment") == "planetary_scenes"
    assert_provides_matches("planetary_scenes", str(Path(planetary_scenes.__file__).parent / "plugin.json"))


def test_a_contributed_scene_gets_its_tree_node(main_window, monkeypatch):
    from SciQLopPlots import ProductsModel
    from SciQLop.components.scenes import registry
    from SciQLop.components.scenes.model import Scene
    from SciQLop.components.scenes.tree import follow_registries
    monkeypatch.setattr(registry.SCENES, "_items", {})
    monkeypatch.setattr(registry.SCENES, "signals", type(registry.SCENES.signals)())
    follow_registries()
    registry.SCENES.contribute(Scene("Tree probe", "earth", "GSM", {}), owner="probe")
    try:
        assert ProductsModel.node(["Scenes", "Tree probe"]) is not None
    finally:
        ProductsModel.instance().remove_node(["Scenes", "Tree probe"])

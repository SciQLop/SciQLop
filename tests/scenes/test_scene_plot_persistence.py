"""Scene plots are saved in templates (spec §5) and restored by name."""
from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel
from SciQLop.core.plot_kinds import PROJECTION
from ..fixtures import *  # noqa: F401, F403

_EARTH = {"scene": "Earth environment", "frame": "GSM", "boundaries": {"magnetopause": "shue1998", "bow_shock": "jelinek2012"}}


def test_a_scene_plot_round_trips_through_a_template(plot_panel, registered, monkeypatch, tmp_path):
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    from SciQLop.user_api.plot import create_plot_panel
    from SciQLop.user_api.scenes import ScenePlot
    sp = plot_panel.plot_scene("Earth environment")
    sp._trajectories.append("speasy//amda//mms1_xyz")  # recorded without fetching: no network in tests
    saved = PanelTemplate.from_panel(plot_panel._get_impl_or_raise())
    assert [(p.kind, p.config) for p in saved.plots] == [
        (PROJECTION, {**_EARTH, "trajectories": ["speasy//amda//mms1_xyz"]})]

    path = tmp_path / "scene.yaml"
    saved.to_file(str(path))
    restored = []
    monkeypatch.setattr(ScenePlot, "add_trajectory", lambda self, source: restored.append(source))
    other = create_plot_panel()._get_impl_or_raise()
    PanelTemplate.from_file(str(path)).apply(other)
    sp2 = next(s for s in map(scene_plot_for, other.plots()) if s is not None)
    assert sp2.scene.name == "Earth environment"
    assert {k: m.name for k, m in sp2._resolved.boundaries.items()} == _EARTH["boundaries"]
    assert restored == ["speasy//amda//mms1_xyz"]


def test_an_unregistered_scene_restores_as_a_placeholder(plot_panel, registered):
    impl = plot_panel._get_impl_or_raise()
    t = PanelTemplate(name="s", plots=[PlotModel(kind=PROJECTION, config={"scene": "nowhere_gsm", "boundaries": {},
                                                                          "trajectories": []})])
    t.apply(impl)
    assert [(p.kind, p.config["scene"]) for p in PanelTemplate.from_panel(impl).plots] == [(PROJECTION, "nowhere_gsm")]


def test_an_unregistered_boundary_keeps_the_scene_default_and_no_placeholder(plot_panel, registered):
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    impl = plot_panel._get_impl_or_raise()
    t = PanelTemplate(name="s", plots=[PlotModel(kind=PROJECTION, config={
        "scene": "Earth environment", "boundaries": {"magnetopause": "nowhere_mp"}, "trajectories": []})])
    t.apply(impl)
    scene_plots = [s for s in map(scene_plot_for, impl.plots()) if s is not None]
    assert len(impl.plots()) == 1 and len(scene_plots) == 1
    assert scene_plots[0]._resolved.boundaries["magnetopause"].name == "shue1998"
    assert [p.kind for p in PanelTemplate.from_panel(impl).plots] == [PROJECTION]

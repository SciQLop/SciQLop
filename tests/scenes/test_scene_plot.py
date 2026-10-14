import numpy as np
import pytest

from SciQLop.components.scenes import registry, summary
from SciQLop.components.scenes.boundary import RadialBoundary
from SciQLop.plugins.planetary_scenes import register_all
from SciQLop.user_api.plot import TimeRange

from ..fixtures import *  # noqa: F401, F403


@pytest.fixture
def earth(monkeypatch):
    from scipy.spatial.transform import Rotation
    from SciQLop.components.scenes import scene_plot
    for reg in (registry.BODIES, registry.BOUNDARIES, registry.SCENES):
        monkeypatch.setattr(reg, "_items", {})
    register_all()
    monkeypatch.setattr(summary, "rotation", lambda f, t, times: Rotation.identity(len(times)))
    monkeypatch.setattr(RadialBoundary, "n_samples", 10)   # 200 costs ~3 s per pane; shapes are time-invariant
    scene_plot._cached_summary.cache_clear()
    yield
    scene_plot._cached_summary.cache_clear()


def wait_for_data(qtbot, graph):
    qtbot.waitUntil(lambda: graph.data() is not None and graph.data()[0] is not None
                    and len(graph.data()[0]) > 0, timeout=5000)


def axis_labels(sp):
    proj = sp.projection._get_impl_or_raise()
    return {a.label() for i in range(proj.subplot_count())
            for a in (proj.subplot(i).x_axis(), proj.subplot(i).y_axis())}


def test_a_scene_plot_has_three_labelled_panes(plot_panel, earth):
    sp = plot_panel.plot_scene("Earth environment")
    assert sp.projection._get_impl_or_raise().subplot_count() == 3
    assert axis_labels(sp) == {"X GSM [R_E]", "Y GSM [R_E]", "Z GSM [R_E]"}


def test_another_body_labels_its_own_frame_and_unit(plot_panel, earth):
    assert axis_labels(plot_panel.plot_scene("Mars environment")) == {"X MSO [R_M]", "Y MSO [R_M]", "Z MSO [R_M]"}


def test_a_model_in_another_frame_is_rotated(plot_panel, earth, qtbot, monkeypatch):
    from scipy.spatial.transform import Rotation
    seen = set()
    monkeypatch.setattr(summary, "rotation",
                        lambda f, t, times: seen.add((f, t)) or Rotation.identity(len(times)))
    plot_panel.plot_scene("Earth environment")   # Jelinek 2012 is a GSE model in a GSM scene
    qtbot.waitUntil(lambda: ("GSM", "GSE") in seen, timeout=5000)


def test_each_pane_draws_its_own_section(plot_panel, earth, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    xy, yz = (sp._boundary_graphs["magnetopause"][pane][0] for pane in (0, 1))
    for g in (xy, yz):
        wait_for_data(qtbot, g)
    x_xy = xy.data()[0]
    assert np.nanmax(x_xy) == pytest.approx(10.251873, abs=0.05)
    assert np.nanmax(np.hypot(*yz.data()[:2])) == pytest.approx(15.427840, abs=0.1)   # terminator ring


def test_a_time_range_change_recomputes(plot_panel, earth, qtbot):
    calls = []
    from SciQLop.components.scenes import scene_plot
    original = scene_plot.pane_summary

    def summary_calls(*a, **k):
        calls.append(a[3:5])
        return original(*a, **k)

    scene_plot.pane_summary = summary_calls
    try:
        plot_panel.plot_scene("Earth environment")
        plot_panel.time_range = TimeRange(0.0, 3600.0)
        qtbot.waitUntil(lambda: (0.0, 3600.0) in set(calls), timeout=5000)
    finally:
        scene_plot.pane_summary = original


def test_boundary_error_shows_on_overlay(plot_panel, earth, qtbot, monkeypatch):
    from SciQLop.components.scenes import scene_plot
    from SciQLop.components.scenes.frames import FrameError

    def down(*a, **k):
        raise FrameError("could not get GSE → GSM matrices from 3DView: connection refused")

    monkeypatch.setattr(scene_plot, "pane_summary", down)
    sp = plot_panel.plot_scene("Earth environment")
    sub = sp.projection._get_impl_or_raise().subplot(0)
    qtbot.waitUntil(lambda: "3DView" in (sub.overlay().text() or ""), timeout=5000)


def test_closing_scene_plot_mid_fetch(plot_panel, earth, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    plot_panel._get_impl_or_raise().remove_plot(sp.projection._get_impl_or_raise())
    qtbot.wait(300)


def test_swapping_a_boundary_replaces_its_curves(plot_panel, earth):
    sp = plot_panel.plot_scene("Earth environment")
    before = len(sp.projection._get_impl_or_raise().subplot(0).plottables())
    sp.set_boundary("magnetopause", "shue1998")
    assert len(sp.projection._get_impl_or_raise().subplot(0).plottables()) == before


def test_a_pane_resolves_to_its_scene_plot(plot_panel, earth):
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    sp = plot_panel.plot_scene("Earth environment")
    other, _ = plot_panel.plot_data(np.arange(10.0), np.arange(10.0))
    assert scene_plot_for(sp.projection._get_impl_or_raise().subplot(1)) is sp
    assert scene_plot_for(other._get_impl_or_raise()) is None

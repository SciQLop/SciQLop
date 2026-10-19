import threading

import numpy as np
import pytest
import shiboken6
from PySide6.QtCore import Qt

from SciQLop.components.scenes import summary
from SciQLop.user_api.plot import TimeRange

from ..fixtures import *  # noqa: F401, F403
from .helpers import overlay_text, proj_of, wait_for_data  # noqa: F401


def pane_labels(sp):
    proj = proj_of(sp)
    return [(proj.subplot(i).x_axis().label(), proj.subplot(i).y_axis().label()) for i in range(proj.subplot_count())]


def expected_labels(frame, unit):
    return [(f"{'XYZ'[i]} {frame} [{unit}]", f"{'XYZ'[j]} {frame} [{unit}]") for i, j in summary.PANES]


def test_a_scene_plot_has_three_labelled_panes(plot_panel, earth):
    sp = plot_panel.plot_scene("Earth environment")
    assert proj_of(sp).subplot_count() == 3
    assert pane_labels(sp) == expected_labels("GSM", "R_E")


def test_another_body_labels_its_own_frame_and_unit(plot_panel, earth):
    assert pane_labels(plot_panel.plot_scene("Mars environment")) == expected_labels("MSO", "R_M")


def test_envelope_curves_are_dashed_and_the_centre_solid(plot_panel, earth):
    sp = plot_panel.plot_scene("Earth environment")
    for pane_graphs in sp._boundary_graphs["magnetopause"].graphs:
        styles = [g.components()[0].pen().style() for g in pane_graphs]
        assert styles == [Qt.PenStyle.SolidLine, Qt.PenStyle.DashLine, Qt.PenStyle.DashLine]


def pane_ranges(proj):
    return [tuple((a.range().start(), a.range().stop()) for a in (proj.subplot(i).x_axis(), proj.subplot(i).y_axis()))
            for i in range(proj.subplot_count())]


def test_a_scene_extent_holds_after_the_data_arrives(plot_panel, earth, fake_speasy, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    sp.add_trajectory("MMS1")
    proj = proj_of(sp)
    orbit = [proj.subplot(i).plottables()[-1] for i in range(3)]   # the projection's own graph keeps no data
    graphs = [g for kind in ("magnetopause", "bow_shock") for pane in sp._boundary_graphs[kind].graphs for g in pane]
    for g in graphs + orbit:
        wait_for_data(qtbot, g)
    qtbot.wait(200)
    assert pane_ranges(proj_of(sp)) == [((-30.0, 30.0), (-30.0, 30.0))] * 3


def test_a_scene_without_extent_fits_its_data(plot_panel, earth, qtbot):
    from SciQLop.components.scenes.model import Scene
    sp = plot_panel.plot_scene(Scene("bare", "earth", "GSM", {}))

    def fitted():
        return all(-2 < x[0] <= -1 and 1 <= x[1] < 2 for x, _ in pane_ranges(proj_of(sp)))   # unit body circle, padded

    # The first-data rescale runs after the plot gets its data, off a fixed schedule: a busy machine needs more than 200 ms.
    qtbot.waitUntil(fitted, timeout=5000)


def test_scene_panes_have_equal_aspect(plot_panel, earth):
    assert proj_of(plot_panel.plot_scene("Earth environment")).equal_aspect_ratio()


def test_a_model_in_another_frame_is_rotated(plot_panel, earth, qtbot, monkeypatch):
    from scipy.spatial.transform import Rotation
    seen = set()
    monkeypatch.setattr(summary, "rotation",
                        lambda f, t, times: seen.add((f, t)) or Rotation.identity(len(times)))
    # A range no other test uses: a late worker of an earlier test can refill the summary cache after the fixture
    # clears it, and a cache hit never rotates.
    plot_panel.time_range = TimeRange(7 * 86400.0, 8 * 86400.0)
    plot_panel.plot_scene("Earth environment")   # Jelinek 2012 is a GSE model in a GSM scene
    qtbot.waitUntil(lambda: ("GSM", "GSE") in seen, timeout=5000)


def test_each_pane_draws_its_own_section(plot_panel, earth, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    xy, yz = (sp._boundary_graphs["magnetopause"].graphs[pane][0] for pane in (0, 1))
    for g in (xy, yz):
        wait_for_data(qtbot, g)
    assert np.nanmax(xy.data()[0]) == pytest.approx(10.251873, abs=0.05)
    assert np.nanmax(np.hypot(*yz.data()[:2])) == pytest.approx(15.427840, abs=0.1)   # terminator ring


def test_a_time_range_change_recomputes(plot_panel, earth, qtbot, monkeypatch):
    from SciQLop.components.scenes import scene_plot
    calls = []
    original = scene_plot.pane_summary

    def recording(*a, **k):
        calls.append(a[3:5])
        return original(*a, **k)

    monkeypatch.setattr(scene_plot, "pane_summary", recording)
    plot_panel.plot_scene("Earth environment")
    plot_panel.time_range = TimeRange(0.0, 3600.0)
    qtbot.waitUntil(lambda: (0.0, 3600.0) in set(calls), timeout=5000)


def test_an_outage_shows_on_every_pane_and_the_plot_recovers(plot_panel, earth, qtbot, monkeypatch):
    from SciQLop.components.scenes import scene_plot
    from SciQLop.components.scenes.frames import FrameError
    original = scene_plot.pane_summary

    def down(*a, **k):
        raise FrameError("could not get GSE → GSM matrices from 3DView: connection refused")

    monkeypatch.setattr(scene_plot, "pane_summary", down)
    sp = plot_panel.plot_scene("Earth environment")
    subs = [proj_of(sp).subplot(i) for i in range(3)]
    qtbot.waitUntil(lambda: all("3DView" in overlay_text(s) for s in subs), timeout=5000)

    monkeypatch.setattr(scene_plot, "pane_summary", original)
    sp.set_boundary("bow_shock", "jelinek2012")
    sp.set_boundary("magnetopause", "shue1998")
    for g in sp._boundary_graphs["magnetopause"].graphs[0]:
        wait_for_data(qtbot, g)
    qtbot.waitUntil(lambda: not any("3DView" in overlay_text(s) for s in subs), timeout=5000)


def test_closing_scene_plot_mid_fetch(plot_panel, earth, qtbot, monkeypatch):
    from SciQLop.components.scenes import scene_plot
    entered, release = threading.Event(), threading.Event()
    original = scene_plot.pane_summary

    def blocking(*a, **k):
        entered.set()
        release.wait(5)
        return original(*a, **k)

    monkeypatch.setattr(scene_plot, "pane_summary", blocking)
    try:
        sp = plot_panel.plot_scene("Earth environment")
        qtbot.waitUntil(entered.is_set, timeout=5000)
        plot_panel._get_impl_or_raise().remove_plot(proj_of(sp))
        qtbot.wait(50)
    finally:
        release.set()
    qtbot.wait(500)


def test_swapping_a_boundary_replaces_its_curves_and_reporters(plot_panel, earth, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    before = len(proj_of(sp).subplot(0).plottables())
    old_reporters = sp._boundary_graphs["magnetopause"].reporters
    sp.set_boundary("magnetopause", "shue1998")
    assert len(proj_of(sp).subplot(0).plottables()) == before
    qtbot.waitUntil(lambda: not any(shiboken6.isValid(r) for r in old_reporters), timeout=2000)


def test_a_pane_resolves_to_its_scene_plot(plot_panel, earth):
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    sp = plot_panel.plot_scene("Earth environment")
    other, _ = plot_panel.plot_data(np.arange(10.0), np.arange(10.0))
    assert scene_plot_for(proj_of(sp).subplot(1)) is sp
    assert scene_plot_for(other._get_impl_or_raise()) is None

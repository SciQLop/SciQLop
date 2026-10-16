import numpy as np
import pytest

from SciQLop.components.scenes import scene_plot
from SciQLop.components.scenes.frames import FrameError
from SciQLop.components.scenes.model import ResolvedScene
from SciQLop.plugins.planetary_scenes import BODIES_DATA, SCENES_DATA

from ..fixtures import *  # noqa: F401, F403
from .helpers import RE, FakeVariable, proj_of, threedview_meta, wait_for_data

EARTH = ResolvedScene(SCENES_DATA[0], BODIES_DATA[0], {})


def fake_variable_for_all(monkeypatch, variable):
    import speasy
    monkeypatch.setattr(speasy, "get_data", lambda *a, **k: variable)


@pytest.fixture
def counted_rotations(monkeypatch):
    from scipy.spatial.transform import Rotation
    calls = []
    monkeypatch.setattr(scene_plot, "rotation",
                        lambda f, to, times: calls.append((f, to)) or Rotation.identity(len(times)))
    return calls


def test_a_3dview_body_is_fetched_in_the_scene_frame_and_scaled(fake_speasy):
    t, x, y, z = scene_plot.trajectory_source("MMS1", EARTH)(0.0, 600.0)
    assert fake_speasy[0][0] == "cdpp3dview/MMS1" and fake_speasy[0][1]["coordinate_frame"] == "GSM"
    assert np.allclose(x, [1.0, 2.0]) and len(t) == 2


def test_a_3dview_product_from_the_speasy_tree_is_fetched_as_a_3dview_body(fake_speasy):
    t, x, y, z = scene_plot.trajectory_source("cdpp3dview/ACE", EARTH)(0.0, 600.0)
    assert fake_speasy[0] == ("cdpp3dview/ACE", {"coordinate_frame": "GSM", "sampling": "600"})
    assert np.allclose(x, [1.0, 2.0])


def test_a_product_is_rotated_into_the_scene_frame(fake_speasy, monkeypatch):
    from scipy.spatial.transform import Rotation
    seen = []
    monkeypatch.setattr(scene_plot, "rotation",
                        lambda f, to, times: seen.append((f, to)) or Rotation.from_euler("x", [[90], [90]], degrees=True))
    t, x, y, z = scene_plot.trajectory_source("cda/X/mms1_mec_r_gse", EARTH)(0.0, 600.0)
    assert seen == [("GSE", "GSM")]
    assert np.allclose(np.stack([x, y, z], axis=1), [[1, 0, 0], [0, 0, 1]], atol=1e-9)   # only 3 columns used


def test_a_3dview_trajectory_in_another_frame_is_refused(monkeypatch, counted_rotations):
    fake_variable_for_all(monkeypatch, FakeVariable([[RE, 0, 0]] * 2, threedview_meta("J2000")))
    with pytest.raises(FrameError, match="J2000.*GSM|GSM.*J2000"):
        scene_plot.trajectory_source("MMS1", EARTH)(0.0, 600.0)


def test_a_3dview_trajectory_without_a_frame_description_is_refused(monkeypatch, counted_rotations):
    fake_variable_for_all(monkeypatch, FakeVariable([[RE, 0, 0]] * 2, {"UNITS": "km"}))
    with pytest.raises(FrameError, match="cannot confirm the frame"):
        scene_plot.trajectory_source("MMS1", EARTH)(0.0, 600.0)


@pytest.mark.parametrize("source", ["MMS1", "cda/X/pos"])
def test_a_range_without_data_draws_nothing(monkeypatch, source):
    fake_variable_for_all(monkeypatch, None)
    assert scene_plot.trajectory_source(source, EARTH)(0.0, 600.0) is None


def test_a_bad_product_never_asks_for_rotations(monkeypatch, counted_rotations):
    fake_variable_for_all(monkeypatch, FakeVariable([[1.0], [2.0]], {"UNITS": "km", "COORDINATE_SYSTEM": "GSE"}))
    with pytest.raises(ValueError, match="is not a position"):
        scene_plot.trajectory_source("cda/X/bt", EARTH)(0.0, 600.0)
    assert counted_rotations == []


def test_an_unknown_unit_is_refused_briefly(monkeypatch, counted_rotations):
    fake_variable_for_all(monkeypatch, FakeVariable([[1, 0, 0]] * 2, {"UNITS": "furlongs", "COORDINATE_SYSTEM": "GSM"}))
    with pytest.raises(ValueError, match=r"^unit 'furlongs' is not a length astropy knows$"):
        scene_plot.trajectory_source("cda/X/pos", EARTH)(0.0, 600.0)


def test_a_unit_that_is_not_a_length_is_refused(monkeypatch, counted_rotations):
    fake_variable_for_all(monkeypatch, FakeVariable([[1, 0, 0]] * 2, {"UNITS": "nT", "COORDINATE_SYSTEM": "GSM"}))
    with pytest.raises(ValueError, match="unit 'nT' is not a length"):
        scene_plot.trajectory_source("cda/X/pos", EARTH)(0.0, 600.0)


@pytest.mark.parametrize("unit", ["Re", "R_E", "RE"])
def test_earth_radii_are_understood(monkeypatch, counted_rotations, unit):
    fake_variable_for_all(monkeypatch, FakeVariable([[2, 0, 0]] * 2, {"UNITS": unit, "COORDINATE_SYSTEM": "GSM"}))
    t, x, y, z = scene_plot.trajectory_source("cda/X/pos", EARTH)(0.0, 600.0)
    assert np.allclose(x, [2.0, 2.0])


def test_the_scene_bodys_own_symbol_means_its_radius(monkeypatch, counted_rotations):
    mars = ResolvedScene(SCENES_DATA[1], next(b for b in BODIES_DATA if b.symbol == "R_M"), {})
    fake_variable_for_all(monkeypatch, FakeVariable([[1, 0, 0]] * 2, {"UNITS": "R_M", "COORDINATE_SYSTEM": "MSO"}))
    t, x, y, z = scene_plot.trajectory_source("cda/X/pos", mars)(0.0, 600.0)
    assert np.allclose(x, [1.0, 1.0])


def test_a_product_without_frame_metadata_is_refused(fake_speasy):
    with pytest.raises(FrameError, match="no COORDINATE_SYSTEM"):
        scene_plot.trajectory_source("cda/X/mms1_pos", EARTH)(0.0, 600.0)


def test_a_frame_3dview_does_not_know_is_refused(fake_speasy):
    with pytest.raises(FrameError, match="RTN"):
        scene_plot.trajectory_source("cda/X/mms1_rtn", EARTH)(0.0, 600.0)


def test_a_product_without_unit_is_refused(fake_speasy, monkeypatch):
    import speasy
    monkeypatch.setattr(speasy, "get_data", lambda *a, **k: FakeVariable([[1, 0, 0]] * 2, {"COORDINATE_SYSTEM": "GSM"}))
    with pytest.raises(ValueError, match="no unit"):
        scene_plot.trajectory_source("cda/X/pos", EARTH)(0.0, 600.0)


def test_a_product_that_is_not_a_position_is_refused(monkeypatch):
    import speasy
    monkeypatch.setattr(speasy, "get_data", lambda *a, **k: FakeVariable(
        [[1.0], [2.0]], {"UNITS": "km", "COORDINATE_SYSTEM": "GSM", "FIELDNAM": "Bt"}))
    with pytest.raises(ValueError, match="Bt is not a position"):
        scene_plot.trajectory_source("cda/X/bt", EARTH)(0.0, 600.0)


def test_a_trajectory_is_drawn_with_time_colouring(plot_panel, earth, fake_speasy, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    proj = proj_of(sp)
    before = len(proj.plottables())
    assert sp.add_trajectory("MMS1") is not None
    assert len(proj.plottables()) == before + 1
    assert proj.time_color_enabled()
    xy_pane = proj.subplot(0).plottables()[-1]   # the projection's own graph keeps no data, its panes do
    wait_for_data(qtbot, xy_pane)
    assert np.allclose(xy_pane.data()[0], [1.0, 2.0])
    assert ("cdpp3dview/MMS1", {"coordinate_frame": "GSM", "sampling": "600"}) in fake_speasy


def test_a_refused_trajectory_shows_on_the_overlay(plot_panel, earth, fake_speasy, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    sp.add_trajectory("cda/X/mms1_rtn")
    qtbot.waitUntil(lambda: "RTN" in (proj_of(sp).subplot(0).overlay().text() or ""), timeout=5000)


def test_a_product_path_is_resolved_once_on_the_main_thread(plot_panel, earth, fake_speasy, qtbot, monkeypatch):
    import threading
    import SciQLopPlots
    from SciQLopPlots import ProductsModelNode
    leaf = ProductsModelNode("mms1_mec_r_gsm", {"speasy_id": "cda/MMS1_MEC/mms1_mec_r_gsm"})
    lookups = []
    monkeypatch.setattr(SciQLopPlots.ProductsModel, "node",
                        lambda path: lookups.append((path, threading.current_thread())) or leaf)
    sp = plot_panel.plot_scene("Earth environment")
    sp.add_trajectory("speasy//cda//MMS//mms1_mec_r_gsm")
    qtbot.waitUntil(lambda: any(p == "cda/MMS1_MEC/mms1_mec_r_gsm" for p, _ in fake_speasy), timeout=5000)
    assert lookups == [(["speasy", "cda", "MMS", "mms1_mec_r_gsm"], threading.main_thread())]


def test_a_product_path_that_is_not_a_speasy_product_is_refused_at_once(plot_panel, earth, monkeypatch):
    import SciQLopPlots
    monkeypatch.setattr(SciQLopPlots.ProductsModel, "node", lambda path: None)
    sp = plot_panel.plot_scene("Earth environment")
    before = len(proj_of(sp).plottables())
    with pytest.raises(ValueError, match="is not a speasy product"):
        sp.add_trajectory("speasy//nowhere")
    assert len(proj_of(sp).plottables()) == before

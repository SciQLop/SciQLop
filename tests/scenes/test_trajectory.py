import numpy as np
import pytest

from SciQLop.components.scenes import scene_plot
from SciQLop.components.scenes.frames import FrameError
from SciQLop.components.scenes.model import ResolvedScene
from SciQLop.plugins.planetary_scenes import BODIES_DATA, SCENES_DATA

from ..fixtures import *  # noqa: F401, F403
from .test_scene_plot import earth, proj_of, wait_for_data  # noqa: F401


class FakeVariable:
    def __init__(self, values, meta):
        self.time = np.array(["2015-10-16T00:00", "2015-10-16T00:10"], dtype="datetime64[ns]")
        self.values = np.asarray(values, dtype=float)
        self.meta = meta
        self.unit = meta.get("UNITS")


EARTH = ResolvedScene(SCENES_DATA[0], BODIES_DATA[0], {})
RE = 6371.2


@pytest.fixture
def fake_speasy(monkeypatch):
    requests = []

    def get_data(product, start, stop, **kwargs):
        requests.append((product, kwargs))
        if product.startswith("cdpp3dview/"):
            return FakeVariable([[RE, 0, 0], [2 * RE, 0, 0]], {"UNITS": "km"})
        if product.endswith("r_gse"):
            return FakeVariable([[RE, 0, 0, RE], [0, RE, 0, RE]], {"UNITS": "km", "COORDINATE_SYSTEM": "GSE>x"})
        if product.endswith("rtn"):
            return FakeVariable([[1, 0, 0]] * 2, {"UNITS": "km", "COORDINATE_SYSTEM": "RTN"})
        if product.endswith("r_gsm"):
            return FakeVariable([[RE, 0, 0]] * 2, {"UNITS": "km", "COORDINATE_SYSTEM": "GSM"})
        return FakeVariable([[1, 0, 0]] * 2, {"UNITS": "km"})

    import speasy
    monkeypatch.setattr(speasy, "get_data", get_data)
    return requests


def test_a_3dview_body_is_fetched_in_the_scene_frame_and_scaled(fake_speasy):
    t, x, y, z = scene_plot.trajectory_source("MMS1", EARTH)(0.0, 600.0)
    assert fake_speasy[0][0] == "cdpp3dview/MMS1" and fake_speasy[0][1]["coordinate_frame"] == "GSM"
    assert np.allclose(x, [1.0, 2.0]) and len(t) == 2


def test_a_product_is_rotated_into_the_scene_frame(fake_speasy, monkeypatch):
    from scipy.spatial.transform import Rotation
    seen = []
    monkeypatch.setattr(scene_plot, "rotation",
                        lambda f, to, times: seen.append((f, to)) or Rotation.from_euler("x", [[90], [90]], degrees=True))
    t, x, y, z = scene_plot.trajectory_source("cda/X/mms1_mec_r_gse", EARTH)(0.0, 600.0)
    assert seen == [("GSE", "GSM")]
    assert np.allclose(np.stack([x, y, z], axis=1), [[1, 0, 0], [0, 0, 1]], atol=1e-9)   # only 3 columns used


def test_a_product_path_is_fetched_by_its_speasy_id(fake_speasy, monkeypatch):
    import SciQLopPlots
    from SciQLopPlots import ProductsModelNode
    leaf = ProductsModelNode("mms1_mec_r_gsm", {"speasy_id": "cda/MMS1_MEC/mms1_mec_r_gsm"})
    paths = []
    monkeypatch.setattr(SciQLopPlots.ProductsModel, "node", lambda path: paths.append(path) or leaf)
    scene_plot.trajectory_source("speasy//cda//MMS//mms1_mec_r_gsm", EARTH)(0.0, 600.0)
    assert paths == [["speasy", "cda", "MMS", "mms1_mec_r_gsm"]]
    assert fake_speasy[0][0] == "cda/MMS1_MEC/mms1_mec_r_gsm"


def test_a_product_path_that_is_not_a_speasy_product_is_refused(fake_speasy, monkeypatch):
    import SciQLopPlots
    monkeypatch.setattr(SciQLopPlots.ProductsModel, "node", lambda path: None)
    with pytest.raises(ValueError, match="is not a speasy product"):
        scene_plot.trajectory_source("speasy//nowhere", EARTH)(0.0, 600.0)


def test_a_range_without_data_draws_nothing(monkeypatch):
    import speasy
    monkeypatch.setattr(speasy, "get_data", lambda *a, **k: None)
    assert scene_plot.trajectory_source("MMS1", EARTH)(0.0, 600.0) is None


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
    assert ("cdpp3dview/MMS1", {"coordinate_frame": "GSM", "sampling": "60"}) in fake_speasy


def test_a_refused_trajectory_shows_on_the_overlay(plot_panel, earth, fake_speasy, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    sp.add_trajectory("cda/X/mms1_rtn")
    qtbot.waitUntil(lambda: "RTN" in (proj_of(sp).subplot(0).overlay().text() or ""), timeout=5000)

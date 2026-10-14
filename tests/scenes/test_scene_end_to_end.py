from pathlib import Path

import numpy as np
import pytest

from SciQLop.user_api.plot import TimeRange

from ..fixtures import *  # noqa: F401, F403
from .helpers import RE, proj_of, threedview_meta, wait_for_data

DATA = Path(__file__).parent / "data"


class RecordedOrbit:
    """MMS1 on 2015-10-16 as 3DView gave it (GSM, km, 10 min samples)."""

    def __init__(self):
        recorded = np.load(DATA / "mms1_gsm_20151016.npz")
        self.time = recorded["time"].astype("datetime64[ns]")
        self.values = recorded["values"]
        self.meta = threedview_meta("GSM")
        self.unit = "km"


@pytest.fixture
def recorded_mms1(monkeypatch):
    import speasy
    orbit = RecordedOrbit()
    monkeypatch.setattr(speasy, "get_data", lambda *a, **k: orbit)
    return orbit


def test_the_mms_orbit_shot_in_three_lines(plot_panel, earth, recorded_mms1, qtbot):
    plot_panel.time_range = TimeRange("2015-10-16", "2015-10-17")
    sp = plot_panel.plot_scene("Earth environment")
    sp.add_trajectory("MMS1")

    proj = proj_of(sp)
    assert proj.time_color_enabled()
    xy_orbit = proj.subplot(0).plottables()[-1]
    wait_for_data(qtbot, xy_orbit)
    x, y = xy_orbit.data()[:2]
    assert np.allclose(x, recorded_mms1.values[:, 0] / RE) and np.allclose(y, recorded_mms1.values[:, 1] / RE)

"""PlotPanel.settle(): block until the panel shows its data, ready to export.

SciQLop.user_api.plot is imported inside tests: a top-level import touches the
ProductsModel Qt global static before a QApplication exists.
"""
import threading
from datetime import datetime, timedelta

import numpy as np
import pytest

from .fixtures import *  # noqa: F401,F403


def _sine(start: float, stop: float):
    x = np.arange(start, stop, 10.0)
    return x, np.sin(x / 300.)


def _y_range(panel):
    r = panel._get_impl_or_raise().plots()[0].y_axis().range()
    return r.start(), r.stop()


def _show_first_hours(panel):
    t0 = datetime(2020, 1, 1)
    panel.time_range = (t0, t0 + timedelta(hours=2))


def test_settle_returns_once_the_axis_fits_the_new_data(plot_panel):
    plot_panel.plot_function(_sine)
    _show_first_hours(plot_panel)

    plot_panel.settle(timeout=10)

    low, high = _y_range(plot_panel)
    assert low < -0.9 and high > 0.9


def test_wait_for_data_returns_once_the_axis_fits_the_new_data(plot_panel):
    plot_panel.plot_function(_sine)
    _show_first_hours(plot_panel)

    assert plot_panel.wait_for_data(timeout=10)

    low, high = _y_range(plot_panel)
    assert low < -0.9 and high > 0.9


def test_settle_raises_when_data_never_arrives(plot_panel):
    release = threading.Event()

    def stuck(start, stop):
        release.wait(5)
        return _sine(start, stop)

    plot_panel.plot_function(stuck)
    _show_first_hours(plot_panel)
    try:
        with pytest.raises(TimeoutError):
            plot_panel.settle(timeout=0.3)
    finally:
        release.set()


def test_settle_on_an_empty_panel_returns(plot_panel):
    plot_panel.settle(timeout=5)

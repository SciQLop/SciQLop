"""Visual time knobs in a real panel: `scope` decides which plots show them."""
from typing import Annotated

import numpy as np
import pytest
from tests.helpers import *  # noqa: F401,F403  — main_window fixture

from SciQLop.user_api.knobs import Knob, SciQLopPlotRange


def _signal(start: float, stop: float):
    t = np.linspace(start, stop, 100)
    return t, np.sin(t)


def _windowed(start: float, stop: float,
              window: SciQLopPlotRange = SciQLopPlotRange(0.3, 0.7)):
    return _signal(start, stop)


def _windowed_on_own_plot(start: float, stop: float,
                          window: Annotated[SciQLopPlotRange, Knob(widget="vspan", scope="plot")]
                          = SciQLopPlotRange(0.3, 0.7)):
    return _signal(start, stop)


def _spans_per_plot(panel):
    from SciQLopPlots import SciQLopPlot, SciQLopVerticalSpan
    impl = panel._get_impl_or_raise()
    by_name = {p.objectName(): p for p in impl.findChildren(SciQLopPlot)}
    return [len(by_name[ptr.objectName()].findChildren(SciQLopVerticalSpan))
            for ptr in impl.plots()]


@pytest.mark.parametrize("callback, expected", [
    (_windowed, [1, 1]),
    (_windowed_on_own_plot, [0, 1]),
])
def test_span_scope_across_panel(qtbot, main_window, callback, expected):
    from SciQLop.user_api import TimeRange
    from SciQLop.user_api.plot import create_plot_panel
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    raw = create_virtual_product(f"scope_test/{callback.__name__}_raw", _signal,
                                 VirtualProductType.Scalar, labels=["raw"])
    windowed = create_virtual_product(f"scope_test/{callback.__name__}", callback,
                                      VirtualProductType.Scalar, labels=["out"])
    panel = create_plot_panel()
    panel.time_range = TimeRange(100.0, 200.0)
    panel.plot(raw)
    panel.plot(windowed)
    qtbot.waitUntil(lambda: _spans_per_plot(panel) == expected, timeout=3000)

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


def _cursor(start: float, stop: float,
            t: Annotated[float, Knob(widget="vline")] = 0.5):
    return _signal(start, stop)


def _cursor_on_own_plot(start: float, stop: float,
                        t: Annotated[float, Knob(widget="vline", scope="plot")] = 0.5):
    return _signal(start, stop)


def _items_per_plot(panel, item_type):
    from SciQLopPlots import SciQLopPlot
    impl = panel._get_impl_or_raise()
    by_name = {p.objectName(): p for p in impl.findChildren(SciQLopPlot)}
    return [len(by_name[ptr.objectName()].findChildren(item_type))
            for ptr in impl.plots()]


@pytest.mark.parametrize("callback, item, expected", [
    (_windowed, "SciQLopVerticalSpan", [1, 1]),
    (_windowed_on_own_plot, "SciQLopVerticalSpan", [0, 1]),
    (_cursor, "SciQLopVerticalLine", [1, 1]),
    # A plot-scoped line is created from Python and Python owns it, so it is no
    # Qt child of its plot: this only shows it did not spread (see test_cursor_knob).
    (_cursor_on_own_plot, "SciQLopVerticalLine", [0, 0]),
])
def test_scope_across_panel(qtbot, main_window, callback, item, expected):
    import SciQLopPlots
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
    item_type = getattr(SciQLopPlots, item)
    qtbot.waitUntil(lambda: _items_per_plot(panel, item_type) == expected, timeout=3000)

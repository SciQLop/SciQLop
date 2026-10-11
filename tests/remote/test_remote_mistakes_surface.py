"""An out-of-process virtual product that cannot be drawn says why, on its plot.

Before: the worker's errors and a colour mismatch only reached the log, and
data outside the requested range drew nothing. The plot just stayed empty.
"""
import itertools

import numpy as np
import pandas as pd
import pytest
from tests.helpers import *  # noqa: F401,F403 — main_window fixture

START, STOP = "2020-01-01T00:00", "2020-01-01T06:00"
_ids = itertools.count()


@pytest.fixture(autouse=True)
def _isolate_registry():
    import SciQLop.components.plotting.backend.remote.registry as reg_mod
    old = reg_mod._REGISTRY
    reg_mod._REGISTRY = None
    yield
    if reg_mod._REGISTRY is not None:
        reg_mod._REGISTRY.shutdown_all()
    reg_mod._REGISTRY = old


# Module-level so cloudpickle ships them by reference.
def raises(start: float, stop: float):
    raise RuntimeError("upstream archive unreachable")


def dataframe(start: float, stop: float):
    return pd.DataFrame({"v": np.ones(100)})


def milliseconds(start: float, stop: float):
    return np.linspace(start, stop, 100) * 1000.0, np.ones(100)


def plain(start: float, stop: float):
    return np.linspace(start, stop, 100), np.ones(100)


def fine(start: float, stop: float):
    return np.linspace(start, stop, 100), np.ones(100)


def _plot_remote_vp(main_window, callback, colored=False):
    from SciQLop.components.plotting.backend.color_axis import ColorAxis
    from SciQLop.user_api.plot import create_plot_panel
    from SciQLop.user_api.virtual_products import VirtualScalar
    vp = VirtualScalar(f"remote_mistakes/vp{next(_ids)}", callback, "v", out_of_process=True,
                       color_axis=ColorAxis(label="c") if colored else None)
    panel = create_plot_panel()
    panel.time_range = (START, STOP)
    plot, _ = panel.plot(vp)
    return plot._get_impl_or_raise()


@pytest.mark.parametrize("callback, colored, expected", [
    (raises, False, "upstream archive unreachable"),
    (dataframe, False, "DataFrame"),
    (milliseconds, False, "none inside the requested range"),
    (plain, True, "Colored"),
])
def test_a_broken_remote_product_says_why_on_its_plot(qtbot, main_window, callback, colored, expected):
    plot = _plot_remote_vp(main_window, callback, colored)
    qtbot.waitUntil(lambda: expected in plot.overlay().text(), timeout=10000)


def test_a_working_remote_product_shows_no_error(qtbot, main_window):
    plot = _plot_remote_vp(main_window, fine)
    qtbot.wait(1500)
    assert plot.overlay().text() == ""

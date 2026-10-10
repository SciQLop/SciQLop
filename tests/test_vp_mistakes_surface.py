"""A virtual product that cannot be drawn says why, on its plot.

Before: an exception in a product callback only reached the log, and several
mistakes (a DataFrame, time in milliseconds, a colour mismatch) silently became
"no data". Either way the user saw an empty plot.
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures
import itertools

import numpy as np
import pandas as pd
import pytest

START, STOP = "2020-01-01T00:00", "2020-01-01T06:00"
_ids = itertools.count()


def _xs(start, stop):
    return np.linspace(start, stop, 100)


def _plot_vp(plot_panel, callback, **kwargs):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product(f"mistakes//vp{next(_ids)}", callback, VirtualProductType.Scalar,
                                labels=["v"], **kwargs)
    plot_panel.time_range = (START, STOP)
    plot, graph = plot_panel.plot(vp)
    return plot._get_impl_or_raise(), graph._get_impl_or_raise()


def _overlay_text_after_fetch(qtbot, plot):
    qtbot.waitUntil(lambda: plot.overlay().text() != "", timeout=5000)
    return plot.overlay().text()


def raises(start: float, stop: float):
    raise RuntimeError("upstream archive unreachable")


def dataframe(start: float, stop: float):
    return pd.DataFrame({"v": np.ones(100)}, index=pd.to_datetime(_xs(start, stop), unit="s"))


def milliseconds(start: float, stop: float):
    return _xs(start, stop) * 1000.0, np.ones(100)


def plain_but_declared_colored(start: float, stop: float):
    return _xs(start, stop), np.ones(100)


@pytest.mark.parametrize("callback, kwargs, expected", [
    (raises, {}, "upstream archive unreachable"),
    (dataframe, {}, "DataFrame"),
    (milliseconds, {}, "none inside the requested range"),
    (plain_but_declared_colored, {"colored": True}, "Colored"),
])
def test_a_broken_virtual_product_says_why_on_its_plot(plot_panel, qtbot, callback, kwargs, expected):
    plot, _ = _plot_vp(plot_panel, callback, **kwargs)
    assert expected in _overlay_text_after_fetch(qtbot, plot)


def test_a_list_is_accepted_like_a_tuple(plot_panel, qtbot):
    def as_list(start: float, stop: float):
        return [_xs(start, stop), np.ones(100)]

    _, graph = _plot_vp(plot_panel, as_list)
    def n_points():
        data = graph.data()
        return len(data[0]) if data and data[0] is not None else 0

    qtbot.waitUntil(lambda: n_points() == 100, timeout=5000)


def test_no_data_is_not_an_error(plot_panel, qtbot):
    def nothing(start: float, stop: float):
        return None

    plot, _ = _plot_vp(plot_panel, nothing)
    qtbot.wait(1000)
    assert plot.overlay().text() == ""

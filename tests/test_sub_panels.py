"""A panel whose content is a sub-panel is not empty.

Before: its "add a product" overlay stayed on top of the sub-panel's plots,
and its time range did not reach the sub-panel.
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures
import numpy as np


def _sine(start: float, stop: float):
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)


def test_the_parent_time_range_reaches_its_sub_panel(plot_panel, qtbot):
    """Fixed in SciQLopPlots 0.51: a time-synced child panel follows its parent."""
    from SciQLop.core import TimeRange
    sub = plot_panel.add_sub_panel()
    sub.plot_function(_sine)
    plot_panel.time_range = TimeRange("2020-01-01", "2020-01-02")
    qtbot.waitUntil(lambda: sub.time_range == plot_panel.time_range, timeout=2000)


def test_adding_a_sub_panel_dismisses_the_empty_panel_overlay(plot_panel):
    impl = plot_panel._get_impl_or_raise()
    assert impl._search_overlay is not None
    plot_panel.add_sub_panel()
    assert impl._search_overlay is None

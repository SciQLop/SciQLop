"""An axis label or scale the user sets wins over the product's metadata.

The product's hints are re-applied when a graph joins the plot and again when
its first data arrives. Each time they overwrote whatever the user had set in
between: the tutorial's log scales, and labels set right after plot().
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures
import threading

import numpy as np

from SciQLop.core.plot_hints import AxisHints, PlotHints


def _sine(start: float, stop: float):
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)


def test_user_axis_settings_survive_the_post_fetch_hints(plot_panel, qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import _get_or_create_registry
    from SciQLop.user_api.plot import ScaleType
    plot, graph = plot_panel.plot_function(_sine, labels=["n"])
    impl = plot._get_impl_or_raise()
    registry = _get_or_create_registry(impl)
    # As with real products: no scale is known until the data arrives.
    key = registry.register(graph._get_impl_or_raise(), PlotHints(y=AxisHints(label="N")))

    plot.set_axis_label("y", "density")
    plot.y_scale_type = ScaleType.Logarithmic
    post_fetch = PlotHints(y=AxisHints(label="Ion density", unit="cm^-3", scale="linear"))
    fetch_thread = threading.Thread(target=registry.update_if_present, args=(key, post_fetch))
    fetch_thread.start()
    fetch_thread.join()
    qtbot.wait(50)  # the post-fetch recompute is deferred to the event loop

    assert impl.y_axis().label() == "density"
    assert plot.y_scale_type == ScaleType.Logarithmic


def test_post_fetch_hints_are_applied_on_the_main_thread(plot_panel, qtbot, monkeypatch):
    """The fetch worker calls update_if_present; reading and writing the axes
    from there raced with the main thread."""
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    plot, graph = plot_panel.plot_function(_sine, labels=["n"])
    registry = tsp._get_or_create_registry(plot._get_impl_or_raise())
    key = registry.register(graph._get_impl_or_raise(), PlotHints(y=AxisHints(label="N")))
    threads = []
    monkeypatch.setattr(tsp, "apply_plot_hints",
                        lambda *a, **k: threads.append(threading.current_thread()))

    fetch_thread = threading.Thread(target=registry.update_if_present,
                                    args=(key, PlotHints(y=AxisHints(label="Ion density"))))
    fetch_thread.start()
    fetch_thread.join()
    qtbot.waitUntil(lambda: bool(threads), timeout=1000)

    assert threads == [threading.main_thread()]

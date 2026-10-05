"""A cacheable product (Speasy, or a VP declared cachable) is fetched with a
margin, so a pan that stays inside the loaded range fetches nothing (GH #143).
A plain VP may return a fixed number of points for any range, so it keeps
exact fetches."""
import numpy as np
import pytest

from tests.fixtures import *  # noqa: F401,F403

T0 = 1_700_000_000.0
SPAN = 3600.0


def _recording_vp(path, calls, cachable):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    def scalar(start: float, stop: float):
        calls.append((start, stop))
        t = np.linspace(start, stop, 16)
        return t, np.sin(t)
    return create_virtual_product(path, scalar, VirtualProductType.Scalar,
                                  labels=["s"], cachable=cachable)


def _plot(qtbot, main_window, path, calls, cachable):
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLop.core import TimeRange
    _recording_vp(path, calls, cachable)
    panel = main_window.new_plot_panel()
    panel = getattr(panel, "_impl", panel)
    panel.set_time_axis_range(TimeRange(T0, T0 + SPAN))
    plot, graph = plot_product(panel, path.split("/"), plot_type=PlotType.TimeSeries)
    qtbot.waitUntil(lambda: len(calls) == 1, timeout=5000)
    return panel, graph


def _pan_by(panel, fraction):
    from SciQLop.core import TimeRange
    start = T0 + fraction * SPAN
    panel.set_time_axis_range(TimeRange(start, start + SPAN))


@pytest.mark.parametrize("cachable, margin", [(True, 0.5), (False, 0.0)])
def test_margin_follows_provider_cacheability(qtbot, main_window, cachable, margin):
    calls = []
    _panel, graph = _plot(qtbot, main_window, f"margin_probe/set_{cachable}", calls, cachable)
    assert graph.prefetch_margin() == pytest.approx(margin)


@pytest.mark.parametrize("cachable", [True, False])
def test_cacheable_products_get_a_prefetch_byte_budget(qtbot, main_window, cachable):
    from SciQLop.components.plotting.ui.time_sync_panel import PREFETCH_BUDGET_BYTES
    calls = []
    _panel, graph = _plot(qtbot, main_window, f"budget_probe/set_{cachable}", calls, cachable)
    assert graph.prefetch_budget_bytes() == (PREFETCH_BUDGET_BYTES if cachable else 0)


def test_pan_inside_margin_does_not_refetch_cacheable_product(qtbot, main_window):
    calls = []
    panel, _graph = _plot(qtbot, main_window, "margin_probe/pan_cached", calls, cachable=True)
    _pan_by(panel, 0.1)
    qtbot.wait(500)
    assert len(calls) == 1


def _plot_trajectory(qtbot, main_window, path, calls, plot_type):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLop.core import TimeRange
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    def trajectory(start: float, stop: float):
        calls.append((start, stop))
        t = np.linspace(start, stop, 16)
        return t, np.cos(t), np.sin(t), t
    create_virtual_product(path, trajectory, VirtualProductType.MultiComponent,
                           labels=["x", "y", "z"], cachable=True)
    panel = main_window.new_plot_panel()
    panel = getattr(panel, "_impl", panel)
    panel.set_time_axis_range(TimeRange(T0, T0 + SPAN))
    plot, graph = plot_product(panel, path.split("/"), plot_type=plot_type)
    qtbot.waitUntil(lambda: len(calls) == 1, timeout=5000)
    return graph


def test_cacheable_projection_fetches_exactly_the_view(qtbot, main_window):
    """A projection has no axis to clip a widened fetch: it would draw every
    prefetched point, e.g. a whole orbit for a one-hour view."""
    from SciQLopPlots import PlotType
    calls = []
    graph = _plot_trajectory(qtbot, main_window, "margin_probe/projection", calls,
                             PlotType.Projections)
    assert graph.prefetch_margin() == 0.0
    assert calls[0] == pytest.approx((T0, T0 + SPAN))


def test_pan_refetches_non_cacheable_product(qtbot, main_window):
    calls = []
    panel, _graph = _plot(qtbot, main_window, "margin_probe/pan_plain", calls, cachable=False)
    _pan_by(panel, 0.1)
    qtbot.waitUntil(lambda: len(calls) == 2, timeout=5000)


"""Projection plots draw their data, static or from a product.

A projection reads its buffers by count (time plus one per pane); an
``(t, (N, 3))`` pair matches no layout and was dropped without a word.
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures
import itertools

import numpy as np

START, STOP = "2020-01-01T00:00", "2020-01-02T00:00"
_ids = itertools.count()


def _orbit(start: float, stop: float):
    t = np.linspace(start, stop, 500)
    phase = (t - t[0]) / 86400 * 2 * np.pi
    return t, np.column_stack([10 * np.cos(phase), 5 * np.sin(phase), 2 * np.sin(2 * phase)])


def _drawn_points(plot):
    """Points held by the 2-D curves of every pane of a projection plot."""
    from SciQLopPlots import SciQLopCurve, SciQLopPlot
    panes = plot._get_impl_or_raise().findChildren(SciQLopPlot)
    curves = [g for pane in panes for g in pane.plottables() if isinstance(g, SciQLopCurve)]
    return sum(len(d[0]) for d in (c.data() for c in curves) if d and d[0] is not None)


def test_static_data_draws_on_a_projection_plot(plot_panel, qtbot):
    from SciQLop.user_api.plot import PlotType
    plot_panel.time_range = (START, STOP)
    t0 = np.datetime64(START, "s").astype("float64")
    plot, _ = plot_panel.plot_data(*_orbit(t0, t0 + 86400), plot_type=PlotType.Projection)
    qtbot.waitUntil(lambda: _drawn_points(plot) > 0, timeout=5000)


def test_a_vector_product_draws_on_a_projection_plot(plot_panel, qtbot):
    from SciQLop.user_api.plot import PlotType
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product(f"projection_draws//vp{next(_ids)}", _orbit,
                                VirtualProductType.Vector, labels=["x", "y", "z"])
    plot_panel.time_range = (START, STOP)
    plot, _ = plot_panel.plot(vp, plot_type=PlotType.Projection)
    qtbot.waitUntil(lambda: _drawn_points(plot) > 0, timeout=10000)


def _panes(plot):
    from SciQLopPlots import SciQLopCurve, SciQLopPlot
    panes = plot._get_impl_or_raise().findChildren(SciQLopPlot)
    return [(pane, next(g for g in pane.plottables() if isinstance(g, SciQLopCurve)))
            for pane in panes if any(isinstance(g, SciQLopCurve) for g in pane.plottables())]


def test_a_named_projection_names_its_curve_and_its_axes(plot_panel):
    from SciQLop.user_api.plot import PlotType
    t0 = np.datetime64(START, "s").astype("float64")
    plot, _ = plot_panel.plot_data(*_orbit(t0, t0 + 86400), plot_type=PlotType.Projection,
                                   name="MMS1 orbit", labels=["X", "Y", "Z"])
    panes = _panes(plot)
    assert [c.labels() for _, c in panes] == [["MMS1 orbit"]] * 3
    assert [(p.x_axis().label(), p.y_axis().label()) for p, _ in panes] == [("X", "Y"), ("Y", "Z"), ("Z", "X")]


def test_a_product_projection_shows_the_product_name_and_its_components_on_the_axes(plot_panel, qtbot):
    from SciQLop.user_api.plot import PlotType
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product(f"projection_draws//orbit{next(_ids)}", _orbit,
                                VirtualProductType.Vector, labels=["x", "y", "z"],
                                display_name="Orbit")
    plot_panel.time_range = (START, STOP)
    plot, _ = plot_panel.plot(vp, plot_type=PlotType.Projection)
    panes = _panes(plot)
    assert [c.labels() for _, c in panes] == [["Orbit"]] * 3
    assert [p.x_axis().label() for p, _ in panes] == ["x", "y", "z"]


def test_product_metadata_hints_leave_projection_plots_alone(plot_panel):
    """A projection plot has no y axis of its own: applying hints to it only
    logged "Abstract method called" for y_axis() and y2_axis()."""
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    from SciQLop.user_api.plot import PlotType
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product(f"projection_draws//vp{next(_ids)}", _orbit,
                                VirtualProductType.Vector, labels=["x", "y", "z"])
    plot, _ = plot_panel.plot(vp, plot_type=PlotType.Projection)
    assert tsp._plot_key(plot._get_impl_or_raise()) not in tsp._PLOT_REGISTRIES


def _position_with_magnitude(start: float, stop: float):
    t, xyz = _orbit(start, stop)
    return t, np.column_stack([xyz, np.linalg.norm(xyz, axis=1)])


def test_a_position_with_its_magnitude_draws_on_a_projection_plot(plot_panel, qtbot):
    """MMS positions (mms1_fgm_r_gsm_srvy_l2) carry x, y, z and |r|: four
    buffers plus time match no layout of the three-pane projection."""
    from SciQLop.user_api.plot import PlotType
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product(f"projection_draws//vp{next(_ids)}", _position_with_magnitude,
                                VirtualProductType.MultiComponent, labels=["x", "y", "z", "|r|"])
    plot_panel.time_range = (START, STOP)
    plot, _ = plot_panel.plot(vp, plot_type=PlotType.Projection)
    qtbot.waitUntil(lambda: _drawn_points(plot) > 0, timeout=10000)

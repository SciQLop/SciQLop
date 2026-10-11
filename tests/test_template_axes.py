"""Templates keep both y axes and which one each graph draws on.

A plot can hold a spectrogram (always on the right axis, y2) and lines on the
left axis, and a line can be moved to y2. Templates only captured the left
axis: a spectrogram's energy axis lost its scale and range, a proxy link
forced it to linear, and a line on y2 came back on y.
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures
import itertools

import numpy as np

START, STOP = "2020-01-01T00:00", "2020-01-01T06:00"
_ids = itertools.count()


def _spectrum(start: float, stop: float):
    t = np.linspace(start, stop, 60)
    return t, np.logspace(1, 4, 32), np.random.rand(60, 32) + 1.0


def _density(start: float, stop: float):
    t = np.linspace(start, stop, 200)
    return t, 10 + np.sin(t / 600.0)


def _vp(callback, kind):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    labels = None if kind == "spectrogram" else ["n"]
    return create_virtual_product(f"template_axes//{callback.__name__}{next(_ids)}", callback,
                                  getattr(VirtualProductType, kind.capitalize()), labels=labels)


def _mixed_plot(plot_panel):
    """A spectrogram on y2 and a line on y, both axes away from their defaults."""
    plot_panel.time_range = (START, STOP)
    plot, _ = plot_panel.plot(_vp(_spectrum, "spectrogram"))
    plot.plot(_vp(_density, "scalar"))
    plot_panel.settle(timeout=30)
    impl = plot._get_impl_or_raise()
    impl.y_axis().set_log(True)
    impl.y_axis().set_range(2.0, 50.0)
    impl.y2_axis().set_log(True)
    impl.y2_axis().set_range(20.0, 5000.0)
    return plot_panel._get_impl_or_raise()


def _template_of(panel):
    from SciQLop.components.plotting.panel_template import PanelTemplate
    return PanelTemplate.from_panel(panel)


def _apply_to_new_panel(template):
    from SciQLop.user_api.plot import create_plot_panel
    target = create_plot_panel()
    template.apply(target._get_impl_or_raise())
    target.settle(timeout=30)
    return target.plots[0]._get_impl_or_raise()


def test_a_template_saves_both_y_axes_and_where_each_graph_draws(plot_panel):
    plot = _template_of(_mixed_plot(plot_panel)).plots[0]
    assert (plot.y_axis.log, plot.y_axis.range) == (True, (2.0, 50.0))
    assert (plot.y2_axis.log, plot.y2_axis.range) == (True, (20.0, 5000.0))
    assert [p.y_axis for p in plot.products] == ["y2", "y"]


def test_a_template_restores_both_y_axes(plot_panel, main_window):
    restored = _apply_to_new_panel(_template_of(_mixed_plot(plot_panel)))
    assert restored.y_axis().log() is True
    assert restored.y2_axis().log() is True


def test_a_line_on_the_right_axis_comes_back_on_the_right_axis(plot_panel, main_window):
    plot_panel.time_range = (START, STOP)
    plot, _ = plot_panel.plot(_vp(_density, "scalar"))
    moved = plot.plot(_vp(_density, "scalar"))
    moved.y_axis = "y2"
    plot_panel.settle(timeout=30)
    template = _template_of(plot_panel._get_impl_or_raise())
    assert [p.y_axis for p in template.plots[0].products] == ["y", "y2"]
    restored = _apply_to_new_panel(template)
    assert [g.y_axis() is restored.y2_axis() for g in restored.plottables()] == [False, True]


def test_a_proxy_link_carries_the_energy_axis_scale(plot_panel):
    from SciQLop.components.plotting.ui.proxy_share import _plot_config
    plot = _template_of(_mixed_plot(plot_panel)).plots[0]
    plot.y_axis.log = False  # the left axis must not leak into the proxy's energy axis
    # The proxy only carries speasy products.
    plot.products = [p.model_copy(update={"kind": "speasy", "speasy_id": f"cda/X/{i}"})
                     for i, p in enumerate(plot.products)]
    assert _plot_config(plot)["y_axis"] == {"log": True}


def test_a_proxy_spectrogram_plot_loads_its_scale_on_the_energy_axis():
    from SciQLop.components.plotting.ui.proxy_share import _plot_model
    plot = _plot_model({"products": [], "y_axis": {"log": True}, "log_z": True}, {})
    assert plot.y2_axis.log is True and plot.y_axis.log is False


def test_a_template_saved_before_right_axes_were_kept_still_loads():
    from SciQLop.components.plotting.panel_template import PanelTemplate
    t = PanelTemplate.model_validate({"name": "old", "plots": [
        {"products": [{"path": "a//b"}], "y_axis": {"log": False, "range": [0, 5]}}]})
    assert t.plots[0].y2_axis is None and t.plots[0].products[0].y_axis == "y"

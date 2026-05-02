"""Regression tests: deleting a layer's inspector extension must tear down
the renderer's visual items (spans/hlines/markers) and signal connections.

Bug: deleting a layer node from the inspector removed the tree node but
left the spans painted on the plot, because the extension was parented to
the renderer (so deleting the extension didn't kill the renderer) and
nothing wired the extension's destruction back to renderer cleanup.
"""
import numpy as np
import pytest
from ..fixtures import *
from SciQLopPlots import PlotType as _PlotType, SciQLopPlot
from SciQLop.user_api.layers.types import Span, HLine
from SciQLop.user_api.data_types import Vector


def _get_sciqlop_plot(plot_panel, qtbot):
    impl = plot_panel._get_impl_or_raise()
    plots = impl.plots()
    if not plots:
        impl.create_plot(0, _PlotType.TimeSeries)
        qtbot.wait(50)
        plots = impl.plots()
    name = plots[0].objectName()
    for child in impl.findChildren(SciQLopPlot):
        if child.objectName() == name:
            return child
    return plots[0]


@pytest.fixture
def panel_with_plot(plot_panel, qtbot):
    plot = _get_sciqlop_plot(plot_panel, qtbot)
    impl = plot_panel._get_impl_or_raise()
    return impl, plot


def _vector_data(n=100):
    t = np.linspace(0, 100, n, dtype=np.float64)
    bx = np.sin(t).astype(np.float64)
    by = np.cos(t).astype(np.float64)
    bz = np.sin(2 * t).astype(np.float64)
    return t, bx, by, bz


class TestRangeOnlyLayerDeletion:
    def test_deleting_extension_clears_spans(self, panel_with_plot, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import wire_layer_renderer

        panel, plot = panel_with_plot

        def hour_grid(start: float, stop: float):
            return [Span(start=start + 1.0, stop=start + 2.0, color="#bdc3c7"),
                    Span(start=start + 3.0, stop=start + 4.0, color="#bdc3c7")]

        renderer = wire_layer_renderer(plot, hour_grid, panel=panel)
        qtbot.wait(50)

        assert len(renderer._spans) == 2, "Spans should be rendered initially"
        assert renderer in plot._layer_renderers

        ext = renderer._layer_ext
        ext.deleteLater()
        qtbot.wait(100)

        assert renderer._disposed is True
        assert renderer._spans == []
        assert renderer not in getattr(plot, "_layer_renderers", [])

    def test_disposed_renderer_does_not_re_render_on_range_change(
            self, panel_with_plot, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import wire_layer_renderer
        from SciQLopPlots import SciQLopPlotRange

        panel, plot = panel_with_plot
        invocations = []

        def my_layer(start: float, stop: float):
            invocations.append((start, stop))
            return [Span(start=start, stop=start + 1.0)]

        renderer = wire_layer_renderer(plot, my_layer, panel=panel)
        qtbot.wait(50)
        initial_calls = len(invocations)

        renderer._layer_ext.deleteLater()
        qtbot.wait(100)

        plot.x_axis().set_range(SciQLopPlotRange(0.0, 50.0))
        qtbot.wait(50)

        assert len(invocations) == initial_calls, \
            "callback should not fire after extension deletion"


class TestLayerWithKnobsDeletion:
    def test_deleting_extension_clears_spans_and_knob_items(
            self, panel_with_plot, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import wire_layer_renderer
        from SciQLop.user_api.knobs.specs import ThresholdKnob

        panel, plot = panel_with_plot

        def my_layer(start: float, stop: float, level: float = 0.0):
            return [HLine(value=level)]

        specs = [ThresholdKnob(name="level", default=0.5)]
        renderer = wire_layer_renderer(plot, my_layer, specs=specs, panel=panel)
        qtbot.wait(50)

        assert len(renderer._hlines) >= 1
        assert len(renderer._visual_knob_items) >= 1

        renderer._knob_inspector_ext.deleteLater()
        qtbot.wait(100)

        assert renderer._disposed is True
        assert renderer._hlines == []
        assert renderer._visual_knob_items == []
        assert renderer not in getattr(plot, "_layer_renderers", [])


class TestDataAwareLayerDeletion:
    def test_deleting_extension_clears_renderer(self, panel_with_plot, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import wire_layer_renderer

        panel, plot = panel_with_plot
        t, bx, by, bz = _vector_data()
        plot.line(t, np.column_stack([bx, by, bz]), labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        def my_layer(data: Vector):
            return [Span(start=0.0, stop=10.0)]

        renderer = wire_layer_renderer(plot, my_layer, panel=panel)
        qtbot.wait(50)
        assert renderer.data_aware is True
        assert len(renderer._spans) == 1

        renderer._layer_ext.deleteLater()
        qtbot.wait(100)

        assert renderer._disposed is True
        assert renderer._spans == []

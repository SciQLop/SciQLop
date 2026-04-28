"""Integration tests for data-aware layers with real Qt plots.

Tests the full lifecycle: introspection, graph matching, signal binding,
deferred binding, data_changed propagation, and the add_layer user API path.
"""
import numpy as np
import pytest
from ..fixtures import *
from SciQLopPlots import (PlotType as _PlotType, SciQLopPlot,
                          SciQLopGraphInterface, SciQLopColorMapInterface)
from SciQLop.user_api.data_types import Scalar, Vector, Spectrogram


def _make_vector_data(n=100):
    t = np.linspace(0, 100, n, dtype=np.float64)
    bx = np.sin(t).astype(np.float64)
    by = np.cos(t).astype(np.float64)
    bz = np.sin(2 * t).astype(np.float64)
    return t, bx, by, bz


def _make_scalar_data(n=100):
    t = np.linspace(0, 100, n, dtype=np.float64)
    y = np.sin(t).astype(np.float64)
    return t, y


def _get_sciqlop_plot(plot_panel, qtbot):
    """Extract the actual SciQLopPlot C++ object from a PlotPanel."""
    impl = plot_panel._get_impl_or_raise()
    plots = impl.plots()
    if not plots:
        impl.create_plot(0, _PlotType.TimeSeries)
        qtbot.wait(50)
        plots = impl.plots()
    if not plots:
        return None
    name = plots[0].objectName()
    for child in impl.findChildren(SciQLopPlot):
        if child.objectName() == name:
            return child
    return plots[0]


@pytest.fixture
def ts_plot(plot_panel, qtbot):
    """Return a real SciQLopPlot (C++) from the panel."""
    plot = _get_sciqlop_plot(plot_panel, qtbot)
    assert plot is not None, "Failed to get SciQLopPlot from panel"
    return plot


# ---------------------------------------------------------------------------
# 1. _find_data_source: does the matcher find the right graph?
# ---------------------------------------------------------------------------

class TestFindDataSource:
    def test_no_plottables_returns_none(self, ts_plot):
        from SciQLop.user_api.layers._renderer import _find_data_source
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        info = DataTypeInfo(product_type="vector")
        assert _find_data_source(ts_plot, info) is None

    def test_finds_vector_graph_by_component_count(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import _find_data_source
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        t, bx, by, bz = _make_vector_data()
        graph = ts_plot.line(t, np.column_stack([bx, by, bz]),
                             labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        assert isinstance(graph, SciQLopGraphInterface)
        assert len(graph.components()) == 3

        info = DataTypeInfo(product_type="vector")
        source = _find_data_source(ts_plot, info)
        assert source is graph

    def test_finds_scalar_graph(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import _find_data_source
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        t, y = _make_scalar_data()
        graph = ts_plot.line(t, y)
        qtbot.wait(50)

        assert len(graph.components()) == 1

        info = DataTypeInfo(product_type="scalar")
        assert _find_data_source(ts_plot, info) is graph

    def test_scalar_filter_rejects_vector(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import _find_data_source
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        t, bx, by, bz = _make_vector_data()
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        info = DataTypeInfo(product_type="scalar")
        assert _find_data_source(ts_plot, info) is None

    def test_any_matches_first_plottable(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import _find_data_source
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        t, bx, by, bz = _make_vector_data()
        graph = ts_plot.line(t, np.column_stack([bx, by, bz]),
                             labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        info = DataTypeInfo(product_type="any")
        assert _find_data_source(ts_plot, info) is graph

    def test_excludes_specified_plottable(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import _find_data_source
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        t, y = _make_scalar_data()
        g1 = ts_plot.line(t, y)
        g2 = ts_plot.line(t, y * 2)
        qtbot.wait(50)

        info = DataTypeInfo(product_type="scalar")
        # Should skip g1, return g2
        result = _find_data_source(ts_plot, info, exclude=g1)
        assert result is g2

    def test_plottables_api_works(self, ts_plot, qtbot):
        """Verify plot.plottables() returns what we expect."""
        t, bx, by, bz = _make_vector_data()
        graph = ts_plot.line(t, np.column_stack([bx, by, bz]),
                             labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        plottables = ts_plot.plottables()
        assert len(plottables) >= 1
        assert graph in plottables


# ---------------------------------------------------------------------------
# 2. LayerRenderer: does binding + update work?
# ---------------------------------------------------------------------------

class TestRendererImmediate:
    """Test binding when the data graph already exists."""

    def test_setup_binds_immediately(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import LayerRenderer
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        t, bx, by, bz = _make_vector_data()
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        def my_layer(data: Vector):
            return []

        info = DataTypeInfo(product_type="vector")
        renderer = LayerRenderer(ts_plot, my_layer, data_type=info, parent=ts_plot)
        renderer.setup_data_binding()

        assert renderer._data_source is not None
        assert renderer._graph_list_connection is None  # no deferred needed

    def test_update_calls_callback_with_data(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import LayerRenderer
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        t, bx, by, bz = _make_vector_data()
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        received_data = []

        def my_layer(data: Vector):
            received_data.append(data)
            return []

        info = DataTypeInfo(product_type="vector")
        renderer = LayerRenderer(ts_plot, my_layer, data_type=info, parent=ts_plot)
        renderer.setup_data_binding()
        renderer.update(0.0, 100.0)

        assert len(received_data) == 1
        d = received_data[0]
        assert isinstance(d, Vector)
        assert len(d) == 100
        assert d.values.ndim == 2
        assert d.values.shape[1] == 3

    def test_data_changed_triggers_callback(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import LayerRenderer
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        t, bx, by, bz = _make_vector_data()
        graph = ts_plot.line(t, np.column_stack([bx, by, bz]),
                             labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        call_count = []

        def my_layer(data: Vector):
            call_count.append(1)
            return []

        info = DataTypeInfo(product_type="vector")
        renderer = LayerRenderer(ts_plot, my_layer, data_type=info, parent=ts_plot)
        renderer.setup_data_binding()
        call_count.clear()

        # Push new data
        t2 = np.linspace(0, 50, 50, dtype=np.float64)
        graph.set_data(t2, np.column_stack([np.sin(t2), np.cos(t2), t2 * 0]))
        qtbot.wait(200)

        assert len(call_count) > 0, "data_changed did not trigger layer callback"

    def test_range_only_layer_not_data_aware(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import LayerRenderer

        def my_layer(start: float, stop: float):
            return []

        renderer = LayerRenderer(ts_plot, my_layer, parent=ts_plot)
        assert not renderer.data_aware
        renderer.setup_data_binding()  # should be a no-op
        assert renderer._data_source is None


# ---------------------------------------------------------------------------
# 3. Deferred binding: graph added AFTER setup_data_binding
# ---------------------------------------------------------------------------

class TestRendererDeferred:
    def test_deferred_bind_connects_graph_list_changed(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import LayerRenderer
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        def my_layer(data: Vector):
            return []

        info = DataTypeInfo(product_type="vector")
        renderer = LayerRenderer(ts_plot, my_layer, data_type=info, parent=ts_plot)
        renderer.setup_data_binding()

        assert renderer._data_source is None
        assert renderer._graph_list_connection is not None

    def test_adding_graph_triggers_deferred_bind(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import LayerRenderer
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        call_count = []

        def my_layer(data: Vector):
            call_count.append(1)
            return []

        info = DataTypeInfo(product_type="vector")
        renderer = LayerRenderer(ts_plot, my_layer, data_type=info, parent=ts_plot)
        renderer.setup_data_binding()
        assert renderer._data_source is None

        # Add graph
        t, bx, by, bz = _make_vector_data()
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(300)

        assert renderer._data_source is not None, \
            "Deferred binding did not find graph after graph_list_changed"
        assert len(call_count) > 0, \
            "Layer callback was not invoked after deferred bind"

    def test_adding_wrong_type_does_not_bind(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import LayerRenderer
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        def my_layer(data: Scalar):
            return []

        info = DataTypeInfo(product_type="scalar")
        renderer = LayerRenderer(ts_plot, my_layer, data_type=info, parent=ts_plot)
        renderer.setup_data_binding()

        # Add a vector graph — should NOT match scalar filter
        t, bx, by, bz = _make_vector_data()
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(300)

        assert renderer._data_source is None, \
            "Scalar layer should not bind to vector graph"

    def test_empty_graph_binds_when_data_arrives(self, ts_plot, qtbot):
        """Simulate async function graph: graph exists but has 0 components
        until set_data populates them. The renderer must bind once data arrives."""
        from SciQLop.user_api.layers._renderer import LayerRenderer
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        call_count = []

        def my_layer(data: Vector):
            call_count.append(1)
            return []

        empty_t = np.empty(0, dtype=np.float64)
        empty_y = np.empty((0, 3), dtype=np.float64)
        graph = ts_plot.line(empty_t, empty_y, labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        info = DataTypeInfo(product_type="vector")
        renderer = LayerRenderer(ts_plot, my_layer, data_type=info, parent=ts_plot)
        renderer.setup_data_binding()

        # Graph exists but may have 0 components — binding might fail initially
        if renderer._data_source is None:
            # Push real data — triggers data_changed which should cause deferred bind
            t, bx, by, bz = _make_vector_data()
            graph.set_data(t, np.column_stack([bx, by, bz]))
            qtbot.wait(300)

            assert renderer._data_source is not None, \
                "Renderer did not bind after data arrived on existing graph"
            assert len(call_count) > 0, \
                "Callback not invoked after late data arrival"

    def test_graph_list_changed_disconnects_after_bind(self, ts_plot, qtbot):
        from SciQLop.user_api.layers._renderer import LayerRenderer
        from SciQLop.user_api.layers._introspection import DataTypeInfo

        def my_layer(data: Vector):
            return []

        info = DataTypeInfo(product_type="vector")
        renderer = LayerRenderer(ts_plot, my_layer, data_type=info, parent=ts_plot)
        renderer.setup_data_binding()
        assert renderer._graph_list_connection is not None

        t, bx, by, bz = _make_vector_data()
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(300)

        assert renderer._graph_list_connection is None, \
            "graph_list_changed listener should disconnect after successful bind"


# ---------------------------------------------------------------------------
# 4. wire_layer_renderer: full wiring path
# ---------------------------------------------------------------------------

class TestWireLayerRenderer:
    def test_wire_detects_data_aware(self, ts_plot, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import wire_layer_renderer

        t, bx, by, bz = _make_vector_data()
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        invocations = []

        def my_layer(data: Vector, threshold: float = 5.0):
            invocations.append("called")
            return []

        renderer = wire_layer_renderer(ts_plot, my_layer)
        assert renderer.data_aware is True
        assert renderer._data_source is not None
        assert len(invocations) > 0, "Initial update should invoke callback"

    def test_wire_deferred_bind(self, ts_plot, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import wire_layer_renderer

        invocations = []

        def my_layer(data: Vector):
            invocations.append("called")
            return []

        renderer = wire_layer_renderer(ts_plot, my_layer)
        assert renderer.data_aware is True
        assert renderer._data_source is None

        t, bx, by, bz = _make_vector_data()
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(300)

        assert renderer._data_source is not None, \
            "wire_layer_renderer deferred bind failed"
        assert len(invocations) > 0, \
            "Callback not invoked after deferred bind"

    def test_wire_range_only_still_works(self, ts_plot, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import wire_layer_renderer
        from SciQLop.user_api.layers.types import HLine

        invocations = []

        def my_layer(start: float, stop: float):
            invocations.append((start, stop))
            return [HLine(value=0.0)]

        renderer = wire_layer_renderer(ts_plot, my_layer)
        assert renderer.data_aware is False
        assert len(invocations) > 0

    def test_wire_data_aware_with_knobs(self, ts_plot, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import wire_layer_renderer

        t, bx, by, bz = _make_vector_data()
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        received_knobs = []

        def my_layer(data: Vector, threshold: float = 5.0, window: int = 10):
            received_knobs.append({"threshold": threshold, "window": window})
            return []

        renderer = wire_layer_renderer(ts_plot, my_layer,
                                        initial_knobs={"threshold": 20.0})
        qtbot.wait(100)

        assert len(received_knobs) > 0
        assert received_knobs[-1]["threshold"] == 20.0
        assert received_knobs[-1]["window"] == 10

    def test_wire_with_mutable_callback_wrapper(self, ts_plot, qtbot):
        """MutableCallback (from register_layer) must preserve type hints."""
        from SciQLop.components.plotting.ui.time_sync_panel import wire_layer_renderer
        from SciQLop.user_api.layers.registry import MutableCallback

        t, bx, by, bz = _make_vector_data()
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        invocations = []

        def my_layer(data: Vector):
            invocations.append("called")
            return []

        wrapper = MutableCallback(my_layer)
        renderer = wire_layer_renderer(ts_plot, wrapper)
        assert renderer.data_aware is True
        assert renderer._data_source is not None
        assert len(invocations) > 0


# ---------------------------------------------------------------------------
# 5. PlotPanel.add_layer: full user API path
# ---------------------------------------------------------------------------

class TestAddLayerAPI:
    def test_add_data_aware_layer_to_panel(self, plot_panel, qtbot):
        """The complete user-facing path: panel.add_layer(func, plot_index=0)."""
        t, bx, by, bz = _make_vector_data()
        ts_plot = _get_sciqlop_plot(plot_panel, qtbot)
        ts_plot.line(t, np.column_stack([bx, by, bz]),
                     labels=["Bx", "By", "Bz"])
        qtbot.wait(50)

        invocations = []

        def magnitude_check(data: Vector, threshold: float = 1.0):
            invocations.append(data)
            return []

        renderer = plot_panel.add_layer(magnitude_check, plot_index=0,
                                         threshold=0.5)
        qtbot.wait(100)

        assert renderer is not None
        assert renderer.data_aware is True
        assert renderer._data_source is not None
        assert len(invocations) > 0, \
            "add_layer callback was never invoked"
        d = invocations[-1]
        assert isinstance(d, Vector), f"Expected Vector, got {type(d)}"
        assert len(d) == 100
        assert d.values.shape[1] == 3

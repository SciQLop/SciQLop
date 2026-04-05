"""Unit tests for pure-logic functions in user_api.plot.

No main_window needed — these test enum converters,
type predicates, path splitting, and array utilities.
All SciQLop imports deferred to test functions (Qt needs QApplication first).
"""
from .fixtures import *
import numpy as np
import pytest


# --- _plots.py: is_product ---

def test_is_product_string(qapp):
    from SciQLop.user_api.plot._plots import is_product
    assert is_product("speasy//amda//imf") is True


def test_is_product_list_of_strings(qapp):
    from SciQLop.user_api.plot._plots import is_product
    assert is_product(["speasy", "amda", "imf"]) is True


def test_is_product_rejects_number(qapp):
    from SciQLop.user_api.plot._plots import is_product
    assert is_product(42) is False


def test_is_product_rejects_mixed_list(qapp):
    from SciQLop.user_api.plot._plots import is_product
    assert is_product(["a", 1]) is False


# --- _plots.py: _split_path ---

def test_split_path_double_slash(qapp):
    from SciQLop.user_api.plot._plots import _split_path
    assert _split_path("a//b//c") == ["a", "b", "c"]


def test_split_path_single_slash(qapp):
    from SciQLop.user_api.plot._plots import _split_path
    assert _split_path("a/b/c") == ["a", "b", "c"]


def test_split_path_no_slash(qapp):
    from SciQLop.user_api.plot._plots import _split_path
    assert _split_path("abc") == ["abc"]


def test_split_path_prefers_double_slash(qapp):
    from SciQLop.user_api.plot._plots import _split_path
    assert _split_path("a//b/c") == ["a", "b/c"]


# --- _plots.py: to_product_path ---

def test_to_product_path_string(qapp):
    from SciQLop.user_api.plot._plots import to_product_path
    assert to_product_path("speasy//amda//imf") == ["speasy", "amda", "imf"]


def test_to_product_path_list(qapp):
    from SciQLop.user_api.plot._plots import to_product_path
    path = ["speasy", "amda", "imf"]
    assert to_product_path(path) is path


def test_to_product_path_invalid(qapp):
    from SciQLop.user_api.plot._plots import to_product_path
    assert to_product_path(42) == []


# --- _plots.py: is_meta_object_instance ---

class _FakeMetaObject:
    def __init__(self, name):
        self._name = name

    def className(self):
        return self._name


class _FakeQObject:
    def __init__(self, class_name):
        self._meta = _FakeMetaObject(class_name)

    def metaObject(self):
        return self._meta


def test_is_meta_object_instance_match(qapp):
    from SciQLop.user_api.plot._plots import is_meta_object_instance
    obj = _FakeQObject("SciQLopTimeSeriesPlot")
    assert is_meta_object_instance(obj, "SciQLopTimeSeriesPlot") is True


def test_is_meta_object_instance_no_match(qapp):
    from SciQLop.user_api.plot._plots import is_meta_object_instance
    obj = _FakeQObject("SciQLopTimeSeriesPlot")
    assert is_meta_object_instance(obj, "SciQLopPlot") is False


def test_is_meta_object_instance_no_metaobject(qapp):
    from SciQLop.user_api.plot._plots import is_meta_object_instance
    assert is_meta_object_instance("plain string", "anything") is False


# --- _graphs.py: is_array_of_double ---

def test_is_array_of_double_true(qapp):
    from SciQLop.user_api.plot._graphs import is_array_of_double
    assert is_array_of_double(np.array([1.0], dtype=np.float64)) is True


def test_is_array_of_double_wrong_dtype(qapp):
    from SciQLop.user_api.plot._graphs import is_array_of_double
    assert is_array_of_double(np.array([1], dtype=np.int32)) is False


def test_is_array_of_double_not_array(qapp):
    from SciQLop.user_api.plot._graphs import is_array_of_double
    assert is_array_of_double([1.0]) is False


# --- _graphs.py: _to_float64 ---

def test_to_float64_none(qapp):
    from SciQLop.user_api.plot._graphs import _to_float64
    assert _to_float64(None) is None


def test_to_float64_already_float64(qapp):
    from SciQLop.user_api.plot._graphs import _to_float64
    a = np.array([1.0, 2.0], dtype=np.float64)
    assert _to_float64(a) is a


def test_to_float64_int_list(qapp):
    from SciQLop.user_api.plot._graphs import _to_float64
    result = _to_float64([1, 2, 3])
    assert result.dtype == np.float64
    np.testing.assert_array_equal(result, [1.0, 2.0, 3.0])


def test_to_float64_int_array(qapp):
    from SciQLop.user_api.plot._graphs import _to_float64
    result = _to_float64(np.array([1, 2], dtype=np.int32))
    assert result.dtype == np.float64


def test_to_float64_datetime64(qapp):
    from SciQLop.user_api.plot._graphs import _to_float64
    dt = np.array(['2020-01-01', '2020-01-02'], dtype='datetime64[ns]')
    result = _to_float64(dt)
    assert result.dtype == np.float64
    assert len(result) == 2


# --- _graphs.py: ensure_arrays_of_double ---

def test_ensure_arrays_of_double(qapp):
    from SciQLop.user_api.plot._graphs import ensure_arrays_of_double
    x = [1, 2, 3]
    y = np.array([4.0, 5.0, 6.0], dtype=np.float64)
    results = list(ensure_arrays_of_double(x, y, None))
    assert results[0].dtype == np.float64
    assert results[1] is y
    assert results[2] is None


# --- _graphs.py: to_plottable ---

def test_to_plottable_none(qapp):
    from SciQLop.user_api.plot._graphs import to_plottable
    assert to_plottable(None) is None


def test_to_plottable_with_gradient(qapp):
    from SciQLop.user_api.plot._graphs import to_plottable, ColorMap

    class _FakeImpl:
        gradient = True

    result = to_plottable(_FakeImpl())
    assert isinstance(result, ColorMap)


def test_to_plottable_without_gradient(qapp):
    from SciQLop.user_api.plot._graphs import to_plottable, Graph

    class _FakeImpl:
        pass

    result = to_plottable(_FakeImpl())
    assert isinstance(result, Graph)


# --- _panel.py: enum converters ---

def test_to_sqp_plot_type_timeseries(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_plot_type
    from SciQLop.user_api.plot.enums import PlotType
    from SciQLopPlots import PlotType as _PlotType
    assert _to_sqp_plot_type(PlotType.TimeSeries) == _PlotType.TimeSeries


def test_to_sqp_plot_type_projection(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_plot_type
    from SciQLop.user_api.plot.enums import PlotType
    from SciQLopPlots import PlotType as _PlotType
    assert _to_sqp_plot_type(PlotType.Projection) == _PlotType.Projections


def test_to_sqp_plot_type_xy(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_plot_type
    from SciQLop.user_api.plot.enums import PlotType
    from SciQLopPlots import PlotType as _PlotType
    assert _to_sqp_plot_type(PlotType.XY) == _PlotType.BasicXY


def test_to_sqp_plot_type_passthrough(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_plot_type
    from SciQLopPlots import PlotType as _PlotType
    assert _to_sqp_plot_type(_PlotType.TimeSeries) == _PlotType.TimeSeries


def test_to_sqp_plot_type_invalid(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_plot_type
    with pytest.raises(ValueError, match="Unknown plot type"):
        _to_sqp_plot_type("invalid")


def test_to_sqp_graph_type_line(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_graph_type
    from SciQLop.user_api.plot.enums import GraphType
    from SciQLopPlots import GraphType as _GraphType
    assert _to_sqp_graph_type(GraphType.Line) == _GraphType.Line


def test_to_sqp_graph_type_curve(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_graph_type
    from SciQLop.user_api.plot.enums import GraphType
    from SciQLopPlots import GraphType as _GraphType
    assert _to_sqp_graph_type(GraphType.Curve) == _GraphType.ParametricCurve


def test_to_sqp_graph_type_colormap(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_graph_type
    from SciQLop.user_api.plot.enums import GraphType
    from SciQLopPlots import GraphType as _GraphType
    assert _to_sqp_graph_type(GraphType.ColorMap) == _GraphType.ColorMap


def test_to_sqp_graph_type_scatter(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_graph_type
    from SciQLop.user_api.plot.enums import GraphType
    from SciQLopPlots import GraphType as _GraphType
    assert _to_sqp_graph_type(GraphType.Scatter) == _GraphType.Scatter


def test_to_sqp_graph_type_passthrough(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_graph_type
    from SciQLopPlots import GraphType as _GraphType
    assert _to_sqp_graph_type(_GraphType.Line) == _GraphType.Line


def test_to_sqp_graph_type_invalid(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_graph_type
    with pytest.raises(ValueError, match="Unknown graph type"):
        _to_sqp_graph_type("invalid")


def test_to_sqp_orientation_horizontal(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_orientation
    from SciQLop.user_api.plot.enums import Orientation
    from PySide6.QtCore import Qt
    assert _to_sqp_orientation(Orientation.Horizontal) == Qt.Orientation.Horizontal


def test_to_sqp_orientation_vertical(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_orientation
    from SciQLop.user_api.plot.enums import Orientation
    from PySide6.QtCore import Qt
    assert _to_sqp_orientation(Orientation.Vertical) == Qt.Orientation.Vertical


def test_to_sqp_orientation_invalid(qapp):
    from SciQLop.user_api.plot._panel import _to_sqp_orientation
    with pytest.raises(ValueError, match="Unknown orientation"):
        _to_sqp_orientation("invalid")


# --- _panel.py: _maybe_product ---

def test_maybe_product_with_string(qapp):
    from SciQLop.user_api.plot._panel import _maybe_product
    from expression import Nothing
    result = _maybe_product("speasy//amda//imf")
    assert result != Nothing
    assert result.value == ["speasy", "amda", "imf"]


def test_maybe_product_with_kwarg(qapp):
    from SciQLop.user_api.plot._panel import _maybe_product
    from expression import Nothing
    result = _maybe_product(product="speasy//amda//imf")
    assert result != Nothing


def test_maybe_product_no_product(qapp):
    from SciQLop.user_api.plot._panel import _maybe_product
    from expression import Nothing
    result = _maybe_product(42)
    assert result == Nothing


def test_maybe_product_empty(qapp):
    from SciQLop.user_api.plot._panel import _maybe_product
    from expression import Nothing
    result = _maybe_product()
    assert result == Nothing


# --- _panel.py: _maybe_callable ---

def test_maybe_callable_with_function(qapp):
    from SciQLop.user_api.plot._panel import _maybe_callable
    from expression import Nothing
    result = _maybe_callable(lambda x: x)
    assert result != Nothing


def test_maybe_callable_with_kwarg(qapp):
    from SciQLop.user_api.plot._panel import _maybe_callable
    from expression import Nothing
    result = _maybe_callable(callback=lambda x: x)
    assert result != Nothing


def test_maybe_callable_not_callable(qapp):
    from SciQLop.user_api.plot._panel import _maybe_callable
    from expression import Nothing
    result = _maybe_callable(42)
    assert result == Nothing


def test_maybe_callable_empty(qapp):
    from SciQLop.user_api.plot._panel import _maybe_callable
    from expression import Nothing
    result = _maybe_callable()
    assert result == Nothing


# --- _panel.py: _speasy_variable_to_arrays ---

def test_speasy_variable_to_arrays_1d(qapp):
    from SciQLop.user_api.plot._panel import _speasy_variable_to_arrays
    from speasy.products.variable import SpeasyVariable
    from speasy.core.data_containers import DataContainer, VariableTimeAxis

    x = np.arange('2020-01-01', '2020-01-04', dtype='datetime64[D]').astype('datetime64[ns]')
    y = np.array([1.0, 2.0, 3.0])
    time_axis = VariableTimeAxis(values=x, meta={})
    values = DataContainer(values=y.reshape(-1, 1), meta={}, name='test', is_time_dependent=True)
    var = SpeasyVariable(values=values, columns=['v'], axes=[time_axis])

    result = _speasy_variable_to_arrays(var)
    assert len(result) == 2
    assert result[0].dtype == np.float64
    assert result[1].dtype == np.float64


def test_speasy_variable_to_arrays_2d(qapp):
    from SciQLop.user_api.plot._panel import _speasy_variable_to_arrays
    from speasy.products.variable import SpeasyVariable
    from speasy.core.data_containers import DataContainer, VariableTimeAxis, VariableAxis

    x = np.arange('2020-01-01', '2020-01-04', dtype='datetime64[D]').astype('datetime64[ns]')
    y_axis = np.array([10.0, 20.0, 30.0])
    z = np.ones((3, 3))
    time_axis = VariableTimeAxis(values=x, meta={})
    freq_axis = VariableAxis(values=y_axis, meta={}, name='freq', is_time_dependent=False)
    values = DataContainer(values=z, meta={}, name='spec', is_time_dependent=True)
    var = SpeasyVariable(values=values, columns=['a', 'b', 'c'], axes=[time_axis, freq_axis])

    result = _speasy_variable_to_arrays(var)
    assert len(result) == 3
    assert result[2].dtype == np.float64

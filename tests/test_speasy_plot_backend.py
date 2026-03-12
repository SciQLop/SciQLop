from .fixtures import *
import pytest
import numpy as np


def test_plot_backend_settings_defaults():
    from SciQLop.components.settings.backend.plot_backend_settings import PlotBackendSettings
    settings = PlotBackendSettings()
    assert settings.default_speasy_backend == "matplotlib"


def test_sciqlop_backend_line_creates_panel(qtbot, qapp, main_window):
    """ax=None should create a new panel and plot into it"""
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend

    backend = SciQLopBackend()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    result = backend.line(x=x, y=y)
    assert result is not None
    plot, graph = result
    assert plot is not None
    assert graph is not None


def test_sciqlop_backend_line_with_panel(qtbot, qapp, main_window):
    """ax=PlotPanel should create a new plot in the given panel"""
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend
    from SciQLop.user_api.plot import create_plot_panel

    backend = SciQLopBackend()
    panel = create_plot_panel()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])

    plot1, graph1 = backend.line(x=x, y=y, ax=panel)
    plot2, graph2 = backend.line(x=x, y=y, ax=panel)
    assert plot1 is not None
    assert plot2 is not None
    assert graph1 is not None
    assert graph2 is not None


def test_sciqlop_backend_line_with_plot(qtbot, qapp, main_window):
    """ax=TimeSeriesPlot should add a graph to the existing plot"""
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend
    from SciQLop.user_api.plot import create_plot_panel

    backend = SciQLopBackend()
    panel = create_plot_panel()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])

    plot, graph1 = backend.line(x=x, y=y, ax=panel)
    returned_plot, graph2 = backend.line(x=x, y=y * 2, ax=plot)
    assert returned_plot is plot


def test_sciqlop_backend_colormap(qtbot, qapp, main_window):
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend

    backend = SciQLopBackend()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([10.0, 20.0, 30.0])
    z = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    result = backend.colormap(x=x, y=y, z=z)
    assert result is not None
    plot, colormap = result
    assert plot is not None
    assert colormap is not None


def test_sciqlop_backend_invalid_ax_raises(qtbot, qapp, main_window):
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend

    backend = SciQLopBackend()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    with pytest.raises(TypeError):
        backend.line(x=x, y=y, ax="not_a_plot")


def test_speasy_variable_plot_with_sciqlop_backend(qtbot, qapp, main_window):
    """End-to-end: register backend, create a SpeasyVariable, call .plot['sciqlop'].line()"""
    import speasy.plotting as splt
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend
    from speasy.products.variable import SpeasyVariable
    from speasy.core.data_containers import DataContainer, VariableTimeAxis

    splt.__backends__["sciqlop"] = SciQLopBackend

    x = np.arange('2020-01-01', '2020-01-02', dtype='datetime64[h]').astype('datetime64[ns]')
    y = np.sin(np.arange(len(x), dtype=float))

    time_axis = VariableTimeAxis(values=x, meta={})
    values = DataContainer(values=y.reshape(-1, 1), meta={}, name='sin', is_time_dependent=True)
    var = SpeasyVariable(values=values, columns=['sin'], axes=[time_axis])

    # Note: var.plot["sciqlop"].line() doesn't work because speasy's Plot.line(backend=None)
    # resets the backend to matplotlib. Use backend= parameter directly instead.
    result = var.plot.line(backend="sciqlop")
    assert result is not None
    plot, graph = result
    assert plot is not None
    assert graph is not None


def test_sciqlop_backend_registered_after_plugin_load(qtbot, qapp, main_window):
    """After the speasy plugin loads (via start_sciqlop), 'sciqlop' should be in __backends__"""
    import speasy.plotting as splt
    assert "sciqlop" in splt.__backends__

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

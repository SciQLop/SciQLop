from tests.helpers import *
import numpy as np
import pytest


class TestPlotWorkflow:
    """Create panels, plot static data and products, verify data."""

    panel = None

    def test_create_panel(self, main_window):
        from SciQLop.user_api.plot import create_plot_panel

        TestPlotWorkflow.panel = create_plot_panel()
        assert TestPlotWorkflow.panel is not None
        assert TestPlotWorkflow.panel._impl is not None

    def test_plot_static_data(self, main_window, qtbot):
        panel = TestPlotWorkflow.panel
        plot, graph = panel.plot([1, 2, 3], [1, 2, 3])
        assert plot is not None
        assert graph is not None
        for _ in range(10000):
            if graph.data is not None and graph.data[0] is not None:
                break
            qtbot.wait(1)
        assert len(graph.data[0])
        assert np.allclose(graph.data[0], [1, 2, 3])
        assert np.allclose(graph.data[1], [1, 2, 3])

    def test_plot_static_spectro(self, main_window, qtbot):
        from SciQLop.user_api.plot import create_plot_panel

        panel = create_plot_panel()
        x = [1, 2, 3]
        y = [1, 2, 3]
        z = [[1, 2, 3], [1, 2, 3], [1, 2, 3]]
        plot, graph = panel.plot(x, y, z)
        assert plot is not None
        assert graph is not None
        for _ in range(10000):
            if graph.data is not None and graph.data[0] is not None:
                break
            qtbot.wait(1)
        assert len(graph.data[0])

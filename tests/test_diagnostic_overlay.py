from .fixtures import *
import pytest


def test_overlay_shows_error(qtbot):
    from PySide6.QtWidgets import QApplication
    from SciQLopPlots import SciQLopPlot
    from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay
    from SciQLop.user_api.virtual_products.validation import Diagnostic

    plot = SciQLopPlot()
    qtbot.addWidget(plot)

    # Create a mock panel whose plots() returns our plot
    class FakePanel:
        def plots(self):
            return [plot]

    overlay = DiagnosticOverlay(FakePanel())
    overlay.show_diagnostics([Diagnostic("error", "ZeroDivisionError in my_func(), line 4")])
    QApplication.processEvents()
    assert overlay.isVisible()
    assert "ZeroDivisionError" in overlay.text()


def test_overlay_shows_success(qtbot):
    from PySide6.QtWidgets import QApplication
    from SciQLopPlots import SciQLopPlot
    from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay

    plot = SciQLopPlot()
    qtbot.addWidget(plot)

    class FakePanel:
        def plots(self):
            return [plot]

    overlay = DiagnosticOverlay(FakePanel())
    overlay.show_success(1000, (1000, 3), "float64", 0.12)
    QApplication.processEvents()
    assert overlay.isVisible()
    assert "1,000 points" in overlay.text()


def test_overlay_clears(qtbot):
    from PySide6.QtWidgets import QApplication
    from SciQLopPlots import SciQLopPlot
    from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay
    from SciQLop.user_api.virtual_products.validation import Diagnostic

    plot = SciQLopPlot()
    qtbot.addWidget(plot)

    class FakePanel:
        def plots(self):
            return [plot]

    overlay = DiagnosticOverlay(FakePanel())
    overlay.show_diagnostics([Diagnostic("error", "some error")])
    QApplication.processEvents()
    overlay.clear()
    QApplication.processEvents()
    assert not overlay.isVisible()


def test_diagnostics_on_a_panel_with_a_projection_show_on_its_first_pane(plot_panel, qtbot):
    import numpy as np
    from SciQLopPlots import GraphType, PlotType
    from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay
    from SciQLop.user_api.virtual_products.validation import Diagnostic
    z = np.zeros(1)
    panel = plot_panel._get_impl_or_raise()
    proj, _ = panel.plot([z, z, z, z], plot_type=PlotType.Projections,
                         graph_type=GraphType.ParametricCurve, labels=["", "", ""])
    overlay = DiagnosticOverlay(panel)
    overlay.show_diagnostics([Diagnostic("error", "ZeroDivisionError in f")])
    qtbot.waitUntil(lambda: "ZeroDivisionError" in proj.subplot(0).overlay().text(), timeout=5000)
    overlay.show_success(10, (10, 3), "float64", 0.1)
    qtbot.waitUntil(lambda: "10 points" in proj.subplot(0).overlay().text(), timeout=5000)
    overlay.clear()
    qtbot.waitUntil(lambda: proj.subplot(0).overlay().text() == "", timeout=5000)

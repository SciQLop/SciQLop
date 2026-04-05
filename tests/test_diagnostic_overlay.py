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
    assert "1000 pts" in overlay.text()


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

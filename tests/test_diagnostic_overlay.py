from .fixtures import *
import pytest


def test_overlay_shows_error(qtbot):
    from PySide6.QtWidgets import QWidget, QApplication
    from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay
    from SciQLop.user_api.virtual_products.validation import Diagnostic

    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(400, 300)
    parent.show()
    overlay = DiagnosticOverlay(parent)
    overlay.show_diagnostics([Diagnostic("error", "ZeroDivisionError in my_func(), line 4")])
    QApplication.processEvents()
    assert overlay.isVisible()
    assert "ZeroDivisionError" in overlay._label.text()


def test_overlay_shows_success(qtbot):
    from PySide6.QtWidgets import QWidget, QApplication
    from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay

    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(400, 300)
    parent.show()
    overlay = DiagnosticOverlay(parent)
    overlay.show_success(1000, (1000, 3), "float64", 0.12)
    QApplication.processEvents()
    assert overlay.isVisible()
    assert "1000 pts" in overlay._label.text()


def test_overlay_clears(qtbot):
    from PySide6.QtWidgets import QWidget, QApplication
    from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay
    from SciQLop.user_api.virtual_products.validation import Diagnostic

    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(400, 300)
    parent.show()
    overlay = DiagnosticOverlay(parent)
    overlay.show_diagnostics([Diagnostic("error", "some error")])
    QApplication.processEvents()
    overlay.clear()
    QApplication.processEvents()
    assert not overlay.isVisible()

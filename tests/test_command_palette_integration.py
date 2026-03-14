from PySide6 import QtCore
from tests.fixtures import *


def test_palette_opens_in_main_window(qtbot, main_window):
    palette = main_window._command_palette
    palette.toggle()
    assert palette.isVisible()
    assert palette._list.model().rowCount() > 0
    palette.toggle()
    assert not palette.isVisible()


def test_palette_ctrl_k_shortcut(qtbot, qapp, main_window):
    main_window.activateWindow()
    main_window.raise_()
    qapp.processEvents()
    qtbot.keyClick(main_window, QtCore.Qt.Key.Key_K, QtCore.Qt.KeyboardModifier.ControlModifier)
    assert main_window._command_palette.isVisible()
    qtbot.keyClick(main_window._command_palette._input, QtCore.Qt.Key.Key_Escape)
    assert not main_window._command_palette.isVisible()


def test_palette_new_plot_panel(qtbot, main_window):
    palette = main_window._command_palette
    palette.toggle()

    qtbot.keyClicks(palette._input, "new plot")
    qtbot.wait(200)
    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)

    assert not palette.isVisible()
    assert len(main_window.plot_panels()) >= 1

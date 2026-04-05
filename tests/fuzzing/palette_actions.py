from __future__ import annotations

from PySide6 import QtCore

from tests.fuzzing.actions import ui_action
from tests.fuzzing.introspect import count_panels


@ui_action(
    narrate="Toggled command palette (now {result})",
    model_update=lambda model: None,
    verify=lambda main_window, model: True,
)
def toggle_palette(main_window, model):
    palette = main_window._command_palette
    palette.toggle()
    return "visible" if palette.isVisible() else "hidden"


@ui_action(
    narrate="Opened command palette with Ctrl+K",
    model_update=lambda model: None,
    verify=lambda main_window, model: main_window._command_palette.isVisible(),
    settle_timeout_ms=100,
)
def open_palette_shortcut(main_window, model, qtbot):
    from PySide6.QtWidgets import QApplication

    main_window.activateWindow()
    main_window.raise_()
    QApplication.processEvents()
    qtbot.keyClick(
        main_window,
        QtCore.Qt.Key.Key_K,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )


@ui_action(
    narrate="Closed command palette with Escape",
    model_update=lambda model: None,
    verify=lambda main_window, model: not main_window._command_palette.isVisible(),
)
def close_palette_escape(main_window, model, qtbot):
    palette = main_window._command_palette
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Escape)


@ui_action(
    narrate="Executed 'new plot' from command palette",
    model_update=lambda model, result: model.panels.append(result),
    verify=lambda main_window, model: count_panels(main_window) == len(model.panels),
    settle_timeout_ms=200,
)
def palette_new_plot(main_window, model, qtbot):
    palette = main_window._command_palette
    palette.toggle()
    qtbot.keyClicks(palette._input, "new plot")
    qtbot.wait(200)
    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)

    panels_after = set(main_window.plot_panels())
    panels_before = set(model.panels)
    new_panels = panels_after - panels_before
    return new_panels.pop() if new_panels else "unknown"

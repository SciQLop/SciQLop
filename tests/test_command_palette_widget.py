from PySide6 import QtCore
from tests.fixtures import *


def test_palette_opens_and_closes(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow
    from SciQLop.components.command_palette.backend.registry import (CommandRegistry, PaletteCommand)
    from SciQLop.components.command_palette.backend.history import LRUHistory
    from SciQLop.components.command_palette.ui.palette_widget import CommandPalette
    win = QMainWindow()
    win.resize(800, 600)
    registry = CommandRegistry()
    registry.register(PaletteCommand(id="test.cmd", name="Test Command", description="test", callback=lambda: None))
    history = LRUHistory(path="/dev/null", max_size=5)
    palette = CommandPalette(win, registry, history)
    palette.toggle()
    assert palette.isVisible()
    palette.toggle()
    assert not palette.isVisible()


def test_palette_filters_commands(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow
    from SciQLop.components.command_palette.backend.registry import (CommandRegistry, PaletteCommand)
    from SciQLop.components.command_palette.backend.history import LRUHistory
    from SciQLop.components.command_palette.ui.palette_widget import CommandPalette
    win = QMainWindow()
    win.resize(800, 600)
    registry = CommandRegistry()
    registry.register(PaletteCommand(id="plot.new", name="New plot panel", description="create panel", callback=lambda: None))
    registry.register(PaletteCommand(id="view.logs", name="Toggle logs", description="show/hide logs", callback=lambda: None))
    history = LRUHistory(path="/dev/null", max_size=5)
    palette = CommandPalette(win, registry, history)
    palette.toggle()
    qtbot.keyClicks(palette._input, "plot")
    qtbot.wait(50)
    assert palette._list.model().rowCount() >= 1
    first_name = palette._list.model().index(0, 0).data(QtCore.Qt.ItemDataRole.DisplayRole)
    assert "plot" in first_name.lower()


def test_palette_executes_argless_command(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow
    from SciQLop.components.command_palette.backend.registry import (CommandRegistry, PaletteCommand)
    from SciQLop.components.command_palette.backend.history import LRUHistory
    from SciQLop.components.command_palette.ui.palette_widget import CommandPalette
    win = QMainWindow()
    win.resize(800, 600)
    executed = []
    registry = CommandRegistry()
    registry.register(PaletteCommand(id="test.exec", name="Execute Me", description="test", callback=lambda: executed.append(True)))
    history = LRUHistory(path="/dev/null", max_size=5)
    palette = CommandPalette(win, registry, history)
    palette.toggle()
    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)
    assert len(executed) == 1
    assert not palette.isVisible()

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


def test_palette_multi_step_args(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand, CommandArg, Completion,
    )
    from SciQLop.components.command_palette.backend.history import LRUHistory
    from SciQLop.components.command_palette.ui.palette_widget import CommandPalette
    from dataclasses import dataclass

    @dataclass
    class FakeArg(CommandArg):
        _completions: list[Completion] | None = None
        def completions(self, context):
            return self._completions or []

    win = QMainWindow()
    win.resize(800, 600)
    result = {}
    def on_execute(product=None, panel=None):
        result["product"] = product
        result["panel"] = panel

    registry = CommandRegistry()
    registry.register(PaletteCommand(
        id="plot.product", name="Plot product", description="Plot",
        callback=on_execute,
        args=[
            FakeArg(name="product", _completions=[
                Completion(value="B_gsm", display="B_gsm"),
                Completion(value="V_gsm", display="V_gsm"),
            ]),
            FakeArg(name="panel", _completions=[
                Completion(value="Panel 1", display="Panel 1"),
            ]),
        ],
    ))
    history = LRUHistory(path="/dev/null", max_size=5)
    palette = CommandPalette(win, registry, history)
    palette.toggle()

    # Select the command
    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)
    assert palette.isVisible()
    assert palette._list.model().rowCount() == 2

    # Select first product
    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)
    assert palette._list.model().rowCount() == 1

    # Select panel
    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)

    assert not palette.isVisible()
    assert result["product"] == "B_gsm"
    assert result["panel"] == "Panel 1"

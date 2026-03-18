from tests.fixtures import *

def test_harvest_menu_actions(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow, QMenu
    from PySide6.QtGui import QAction
    from SciQLop.components.command_palette.backend.registry import CommandRegistry
    from SciQLop.components.command_palette.backend.harvester import harvest_qactions
    win = QMainWindow()
    menu = QMenu("File", win)
    win.menuBar().addMenu(menu)
    action = QAction("Save", win)
    menu.addAction(action)
    registry = CommandRegistry()
    harvest_qactions(registry, win)
    ids = [c.id for c in registry.commands()]
    assert any("Save" in cid for cid in ids)

def test_harvest_skips_already_registered(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow, QMenu
    from PySide6.QtGui import QAction
    from SciQLop.components.command_palette.backend.registry import (CommandRegistry, PaletteCommand)
    from SciQLop.components.command_palette.backend.harvester import harvest_qactions
    win = QMainWindow()
    menu = QMenu("File", win)
    win.menuBar().addMenu(menu)
    action = QAction("Save", win)
    menu.addAction(action)
    registry = CommandRegistry()
    registry.register(PaletteCommand(
        id="qaction.File.Save", name="Save (rich)", description="rich version", callback=lambda: None,
    ))
    harvest_qactions(registry, win)
    names = [c.name for c in registry.commands()]
    assert names.count("Save (rich)") == 1
    assert "Save" not in names

def test_harvest_skips_replaces_qaction(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow, QMenu
    from PySide6.QtGui import QAction
    from SciQLop.components.command_palette.backend.registry import (CommandRegistry, PaletteCommand)
    from SciQLop.components.command_palette.backend.harvester import harvest_qactions
    win = QMainWindow()
    menu = QMenu("Tools", win)
    win.menuBar().addMenu(menu)
    action = QAction("Open JupyterLab in browser", win)
    menu.addAction(action)
    registry = CommandRegistry()
    registry.register(PaletteCommand(
        id="jupyter.console", name="Jupyter Console", description="Start console",
        callback=lambda: None, replaces_qaction="Open JupyterLab in browser",
    ))
    harvest_qactions(registry, win)
    names = [c.name for c in registry.commands()]
    assert "Open JupyterLab in browser" not in names

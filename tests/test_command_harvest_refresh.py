"""A plugin activated after startup gets its menu-bar actions into the command palette (spec §9 issue 3)."""
import json
import textwrap

import pytest
from PySide6.QtWidgets import QMainWindow

from SciQLop.components.command_palette.backend.registry import COMMANDS
from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.core import extensions


@pytest.fixture
def fresh(qapp):
    saved = (dict(context.STATES), set(loader._attempted), dict(vars(loader.loaded_plugins)),
             dict(extensions._EXTENSION_POINTS))
    before = {c.id for c in COMMANDS.list()}
    yield
    for cid in [c.id for c in COMMANDS.list() if c.id not in before]:
        COMMANDS.remove(cid)
    for live, old in zip((context.STATES, loader._attempted, vars(loader.loaded_plugins),
                          extensions._EXTENSION_POINTS), saved):
        live.clear()
        live.update(old)


def _plugin(folder, name, code):
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(code))
    (pkg / "plugin.json").write_text(json.dumps({"name": name, "version": "1.0.0"}))
    return (str(folder), name)


def test_a_live_loaded_plugins_menu_action_reaches_the_palette(qtbot, tmp_path, fresh):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.menuBar().addMenu("Tools").addAction("Existing tool")
    plugin = _plugin(tmp_path, "hv_late", """
        def load(main_window):
            main_window.menuBar().actions()[0].menu().addAction("Late plugin tool")
    """)
    loader.activate_all([plugin], main_window=window, ep_plugins={})
    names = [c.name for c in COMMANDS.list()]
    assert "Late plugin tool" in names
    assert names.count("Existing tool") == 1


def test_refreshing_twice_adds_nothing(qtbot, fresh):
    from SciQLop.components.command_palette.backend.harvester import refresh_harvest
    window = QMainWindow()
    qtbot.addWidget(window)
    window.menuBar().addMenu("Tools").addAction("Once only")
    refresh_harvest(window)
    count = len(COMMANDS.list())
    refresh_harvest(window)
    assert len(COMMANDS.list()) == count
    assert [c.name for c in COMMANDS.list()].count("Once only") == 1


def test_main_windows_without_a_menu_bar_are_ignored(qapp):
    from SciQLop.components.command_palette.backend.harvester import refresh_harvest
    refresh_harvest(object())


def _replaced_action_window(qtbot):
    from SciQLop.components.command_palette.backend.registry import CommandRegistry, PaletteCommand
    CommandRegistry().register(PaletteCommand(
        id="test.replacer", name="Replacement", description="", callback=lambda: None,
        replaces_qaction="Replaced action"))
    window = QMainWindow()
    qtbot.addWidget(window)
    window.menuBar().addMenu("Tools").addAction("Replaced action")
    return window


def test_actions_replaced_by_a_command_are_not_harvested(qtbot, fresh):
    from SciQLop.components.command_palette.backend.harvester import refresh_harvest
    refresh_harvest(_replaced_action_window(qtbot))
    assert "Replaced action" not in [c.name for c in COMMANDS.list()]


def test_actions_replaced_by_a_command_are_not_harvested_after_activation(qtbot, tmp_path, fresh):
    window = _replaced_action_window(qtbot)
    plugin = _plugin(tmp_path, "hv_noop", "def load(main_window):\n    pass\n")
    loader.activate_all([plugin], main_window=window, ep_plugins={})
    assert "Replaced action" not in [c.name for c in COMMANDS.list()]

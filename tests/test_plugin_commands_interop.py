"""Interop proof for commands, menu entries and shortcuts: one plugin contributes a command, a menu entry, a shortcut
and a menu-bar QAction; a failing plugin's command is withdrawn and a menu entry naming it is left out."""
import json
import sys
import textwrap

import pytest
from PySide6.QtWidgets import QMainWindow, QMenu

from SciQLop.components.command_palette.backend.registry import COMMANDS, CommandRegistry
from SciQLop.components.command_palette.menu_entries import add_menu_entries
from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.components.shortcuts.registry import key_for
from SciQLop.core import extensions

from .helpers import restore_extension_points

_OWNERS = ("ci_vdf", "ci_broken")


@pytest.fixture
def fresh(qapp):
    saved = (dict(context.STATES), set(loader._attempted), dict(vars(loader.loaded_plugins)))
    saved_points = dict(extensions._EXTENSION_POINTS)
    yield
    for ep in extensions.all_extension_points():
        for owner in _OWNERS:
            ep.remove_owner(owner)
    for command in [c for c in CommandRegistry().commands() if c.id.startswith("qaction.VDF")]:
        CommandRegistry().unregister(command.id)
    for live, old in zip((context.STATES, loader._attempted, vars(loader.loaded_plugins)), saved):
        live.clear()
        live.update(old)
    restore_extension_points(saved_points)


def _plugin(folder, name, code, **desc):
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(code))
    (pkg / "plugin.json").write_text(json.dumps({"name": name, "version": "1.0.0", **desc}))
    return (str(folder), name)


_VDF = """
    from SciQLop.components.command_palette.arg_types import PanelArg
    from SciQLop.components.command_palette.backend.registry import PaletteCommand
    from SciQLop.components.shortcuts.registry import Shortcut
    from SciQLop.core.menus import MenuEntry

    FITTED = []

    def activate(ctx):
        ctx.contribute("sciqlop.commands", PaletteCommand(
            "ci_vdf.fit", "Fit VDF", "", callback=lambda panel: FITTED.append(panel), args=[PanelArg("panel")]))
        ctx.contribute("sciqlop.menus", MenuEntry(
            "ci_vdf.fit_in_panel", "panel", "ci_vdf.fit", when=lambda c: c.get("panel", "").startswith("Event")))
        ctx.contribute("sciqlop.shortcuts", Shortcut("ci_vdf.fit", "VDF", "Fit VDF", "Ctrl+Alt+V"))
        ctx.main_window.menuBar().addMenu("VDF").addAction("Open VDF browser")
"""

_BROKEN = """
    from SciQLop.components.command_palette.backend.registry import PaletteCommand

    def activate(ctx):
        ctx.contribute("sciqlop.commands", PaletteCommand("ci_broken.go", "Broken go", "", callback=lambda: None))
        raise RuntimeError("boom")
"""


def _names(actions):
    return [a.text() for a in actions]


def test_plugin_contributes_command_menu_entry_shortcut_and_qaction(tmp_path, qtbot, fresh):
    window = QMainWindow()
    qtbot.addWidget(window)
    loader.activate_all([_plugin(tmp_path, "ci_vdf", _VDF)], main_window=window, ep_plugins={})
    assert context.STATES["ci_vdf"].status == "active", context.STATES["ci_vdf"].reason

    palette_names = {c.name for c in CommandRegistry().commands()}
    assert {"Fit VDF", "Open VDF browser"} <= palette_names

    menu = QMenu()
    actions = add_menu_entries(menu, "panel", {"panel": "Event 1"})
    assert _names(actions) == ["Fit VDF"]
    actions[0].trigger()
    assert sys.modules["ci_vdf"].FITTED == ["Event 1"]

    assert add_menu_entries(QMenu(), "panel", {"panel": "Other"}) == []
    assert key_for("ci_vdf.fit") == "Ctrl+Alt+V"


def test_failing_plugin_withdraws_its_command_and_menu_entries_naming_it_are_left_out(tmp_path, qtbot, fresh):
    from SciQLop.core.menus import MENUS, MenuEntry
    window = QMainWindow()
    qtbot.addWidget(window)
    loader.activate_all([_plugin(tmp_path, "ci_broken", _BROKEN)], main_window=window, ep_plugins={})
    assert context.STATES["ci_broken"].status != "active"
    assert "ci_broken.go" not in COMMANDS

    MENUS.contribute(MenuEntry("ci_broken.entry", "panel", "ci_broken.go"), owner="ci_broken")
    assert add_menu_entries(QMenu(), "panel", {"panel": "Event 1"}) == []

"""Keyboard shortcuts are contributions to sciqlop.shortcuts; the published helpers keep working."""
import pytest

from SciQLop.components.shortcuts.registry import (SHORTCUTS, Shortcut, key_for, register_shortcut,
                                                    registered_shortcuts)
from SciQLop.core.extensions import owned_by


@pytest.fixture
def withdraw(qapp):
    yield
    SHORTCUTS.remove_owner("sc_demo")


def test_builtin_shortcuts_are_owned_by_sciqlop(qapp):
    assert SHORTCUTS.owner_of("app.command_palette") == "sciqlop"
    assert key_for("app.command_palette") == "Ctrl+K"


def test_a_plugin_shortcut_is_registered_listed_and_bound(withdraw):
    with owned_by("sc_demo"):
        register_shortcut(Shortcut("sc_demo.fit", "VDF", "Fit the distribution", "Ctrl+Alt+F"))
    assert SHORTCUTS.owner_of("sc_demo.fit") == "sc_demo"
    assert "sc_demo.fit" in [s.id for s in registered_shortcuts()]
    assert key_for("sc_demo.fit") == "Ctrl+Alt+F"


def test_unknown_ids_still_raise_key_error(qapp):
    with pytest.raises(KeyError):
        key_for("sc_nowhere.nothing")


def test_a_withdrawn_shortcut_unbinds_and_later_bindings_keep_following_rebinds(withdraw, monkeypatch):
    from PySide6.QtGui import QAction
    from SciQLop.components.shortcuts import registry
    monkeypatch.setattr(registry, "_overrides", None)
    with owned_by("sc_demo"):
        register_shortcut(Shortcut("sc_demo.gone", "VDF", "Soon gone", "Ctrl+Alt+G"))
    dead, alive = QAction(), QAction()
    registry.bind_shortcut(dead, "sc_demo.gone")
    registry.bind_shortcut(alive, "panel.autoscale_all")
    SHORTCUTS.remove_owner("sc_demo")
    registry._on_settings_changed("shortcuts", {"panel.autoscale_all": "Ctrl+Alt+9"})
    assert alive.shortcut().toString() == "Ctrl+Alt+9"
    assert dead.shortcut().isEmpty()


def test_the_published_adapters_are_marshalled_from_the_kernel_thread(withdraw, monkeypatch):
    import threading
    from SciQLop.components.command_palette.backend.registry import CommandRegistry, PaletteCommand
    from SciQLop.user_api import threading as sq_threading
    marshalled = []
    monkeypatch.setattr(sq_threading, "_invoker", lambda func, *a, **kw: marshalled.append(func))
    worker = threading.Thread(target=lambda: (
        CommandRegistry().register(PaletteCommand(id="sc_demo.cmd", name="n", description="", callback=print)),
        CommandRegistry().unregister("sc_demo.cmd"),
        register_shortcut(Shortcut("sc_demo.kernel", "VDF", "From a cell", "Ctrl+Alt+K"))))
    worker.start()
    worker.join()
    assert len(marshalled) == 3


def test_the_help_lists_a_shortcut_registered_while_it_is_open(qtbot, withdraw):
    from SciQLop.components.shortcuts.ui import ShortcutsHelp
    dialog = ShortcutsHelp()
    qtbot.addWidget(dialog)
    with owned_by("sc_demo"):
        register_shortcut(Shortcut("sc_demo.late", "VDF", "Late shortcut", "Ctrl+Alt+L"))
    assert "Late shortcut" in [label for label, _key in dialog.rows()]


def test_the_settings_editor_gets_a_row_for_a_shortcut_registered_while_it_is_open(qtbot, withdraw):
    from SciQLop.components.shortcuts.ui import ShortcutsEditor
    editor = ShortcutsEditor()
    qtbot.addWidget(editor)
    with owned_by("sc_demo"):
        register_shortcut(Shortcut("sc_demo.settings", "VDF", "Settings shortcut", "Ctrl+Alt+S"))
    assert editor.key_edit("sc_demo.settings") is not None

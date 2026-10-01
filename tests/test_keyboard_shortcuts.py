"""Every SciQLop shortcut lives in one registry, can be changed from Settings,
and is listed in the read-only Help > Keyboard shortcuts panel."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QKeySequenceEdit, QWidget

from .fixtures import *  # noqa: F401, F403


@pytest.fixture
def customize():
    from SciQLop.components.shortcuts import KeyboardShortcutsSettings

    def _set(overrides: dict):
        with KeyboardShortcutsSettings() as settings:
            settings.shortcuts = dict(overrides)

    yield _set
    _set({})


def test_key_for_is_the_default_until_the_user_changes_it(customize):
    from SciQLop.components.shortcuts import key_for
    assert key_for("app.command_palette") == "Ctrl+K"
    customize({"app.command_palette": "Ctrl+P"})
    assert key_for("app.command_palette") == "Ctrl+P"


def test_a_bound_qshortcut_follows_the_user_change_live(qtbot, customize):
    from SciQLop.components.shortcuts import add_shortcut
    host = QWidget()
    qtbot.addWidget(host)
    shortcut = add_shortcut(host, "panel.organize", lambda: None)
    assert shortcut.key() == QKeySequence("O")
    assert shortcut.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut

    customize({"panel.organize": "Ctrl+Shift+O"})

    assert shortcut.key() == QKeySequence("Ctrl+Shift+O")


def test_clearing_a_shortcut_disables_it(qtbot, customize):
    from SciQLop.components.shortcuts import add_shortcut
    host = QWidget()
    qtbot.addWidget(host)
    shortcut = add_shortcut(host, "panel.organize", lambda: None)
    customize({"panel.organize": ""})
    assert shortcut.key().isEmpty()


def test_a_deleted_binding_owner_is_left_alone_on_change(qtbot, customize):
    import shiboken6
    from SciQLop.components.shortcuts import bind_shortcut, bind_tooltip
    host = QWidget()
    action = QAction("Full screen", host)
    bind_shortcut(action, "app.full_screen")
    bind_tooltip(action, "app.full_screen", "Full screen")
    shiboken6.delete(host)

    with qtbot.captureExceptions() as exceptions:
        customize({"app.full_screen": "F12"})

    assert exceptions == []


def test_changing_a_shortcut_after_a_main_window_is_destroyed_is_silent(
        qapp, sciqlop_resources, qtbot, customize):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from tests.fixtures import destroy_main_window
    destroy_main_window(SciQLopMainWindow())

    with qtbot.captureExceptions() as exceptions:
        customize({"app.full_screen": "F12"})

    assert exceptions == []


def test_a_bound_qaction_follows_the_user_change_live(qtbot, customize):
    from SciQLop.components.shortcuts import bind_shortcut
    host = QWidget()
    qtbot.addWidget(host)
    action = QAction("Full screen", host)
    bind_shortcut(action, "app.full_screen")
    assert action.shortcut() == QKeySequence("F11")
    customize({"app.full_screen": "F12"})
    assert action.shortcut() == QKeySequence("F12")


def test_a_plugin_can_register_its_own_shortcut():
    from SciQLop.components.shortcuts import Shortcut, register_shortcut, registered_shortcuts, key_for
    register_shortcut(Shortcut("test_plugin.do_it", "Test plugin", "Do it", "Ctrl+Alt+J"))
    assert key_for("test_plugin.do_it") == "Ctrl+Alt+J"
    assert "test_plugin.do_it" in {s.id for s in registered_shortcuts()}


def test_builtin_defaults_do_not_conflict():
    from SciQLop.components.shortcuts import conflicts
    assert conflicts({}) == {}


def test_two_actions_on_the_same_key_are_reported_as_conflicts():
    from SciQLop.components.shortcuts import conflicts
    found = conflicts({"panel.organize": "M"})
    assert found["panel.organize"] == ["plot.autoscale"]
    assert found["plot.autoscale"] == ["panel.organize"]


def test_the_editor_stores_only_keys_that_differ_from_the_default(qtbot):
    from SciQLop.components.shortcuts.ui import ShortcutsEditor
    editor = ShortcutsEditor()
    qtbot.addWidget(editor)
    editor.set_value({})
    emitted = []
    editor.value_changed.connect(emitted.append)

    editor.key_edit("panel.organize").setKeySequence(QKeySequence("Ctrl+Shift+O"))
    assert emitted[-1] == {"panel.organize": "Ctrl+Shift+O"}

    editor.key_edit("panel.organize").setKeySequence(QKeySequence("O"))
    assert emitted[-1] == {}


def test_the_editor_keeps_changes_to_shortcuts_it_does_not_list(qtbot):
    """A disabled plugin's shortcut is not registered this session; editing
    another shortcut must not wipe the user's choice for it."""
    from SciQLop.components.shortcuts.ui import ShortcutsEditor
    editor = ShortcutsEditor()
    qtbot.addWidget(editor)
    editor.set_value({"unloaded_plugin.action": "Ctrl+Alt+U"})
    emitted = []
    editor.value_changed.connect(emitted.append)

    editor.key_edit("panel.organize").setKeySequence(QKeySequence("Ctrl+Shift+O"))

    assert emitted[-1] == {"unloaded_plugin.action": "Ctrl+Alt+U", "panel.organize": "Ctrl+Shift+O"}


def test_the_editor_reset_button_restores_the_default(qtbot):
    from SciQLop.components.shortcuts.ui import ShortcutsEditor
    editor = ShortcutsEditor()
    qtbot.addWidget(editor)
    editor.set_value({"panel.organize": "Ctrl+Shift+O"})
    emitted = []
    editor.value_changed.connect(emitted.append)

    editor.reset_button("panel.organize").click()

    assert editor.key_edit("panel.organize").keySequence() == QKeySequence("O")
    assert emitted[-1] == {}


def test_the_editor_flags_conflicting_keys(qtbot):
    from SciQLop.components.shortcuts.ui import ShortcutsEditor
    editor = ShortcutsEditor()
    qtbot.addWidget(editor)
    editor.set_value({"panel.organize": "M"})
    assert "Autoscale" in editor.conflict_text("panel.organize")
    assert editor.conflict_text("app.full_screen") == ""


def test_shortcuts_setting_uses_the_shortcuts_editor():
    from SciQLop.components.shortcuts import KeyboardShortcutsSettings
    from SciQLop.components.shortcuts.ui import ShortcutsEditor
    from SciQLop.components.settings.ui.settings_delegates import get_delegate_for_field
    field = KeyboardShortcutsSettings.model_fields["shortcuts"]
    assert isinstance(get_delegate_for_field("shortcuts", field), ShortcutsEditor)


def test_the_help_panel_lists_every_shortcut_read_only(qtbot, customize):
    from SciQLop.components.shortcuts import registered_shortcuts
    from SciQLop.components.shortcuts.ui import ShortcutsHelp
    customize({"panel.organize": "Ctrl+Shift+O"})
    help_panel = ShortcutsHelp()
    qtbot.addWidget(help_panel)

    rows = help_panel.rows()

    assert {label for label, _ in rows} >= {s.label for s in registered_shortcuts()}
    assert dict(rows)["Organize plots"] == QKeySequence("Ctrl+Shift+O").toString(
        QKeySequence.SequenceFormat.NativeText)
    assert not help_panel.findChildren(QKeySequenceEdit)


def test_the_help_panel_filter_narrows_the_list(qtbot):
    from SciQLop.components.shortcuts.ui import ShortcutsHelp
    help_panel = ShortcutsHelp()
    qtbot.addWidget(help_panel)
    help_panel.filter.setText("log scale")
    assert [label for label, _ in help_panel.rows(visible_only=True)] == [
        "Toggle log scale of the hovered or selected axis"]


def test_help_menu_opens_the_shortcuts_panel(main_window):
    from SciQLop.components.shortcuts.ui import ShortcutsHelp
    action = main_window.shortcutsHelpAction
    assert action in main_window.helpMenu.actions()
    assert action.shortcut() == QKeySequence("F1")
    action.trigger()
    panels = main_window.findChildren(ShortcutsHelp)
    assert len(panels) == 1 and panels[0].isVisible()
    action.trigger()
    assert len(main_window.findChildren(ShortcutsHelp)) == 1
    panels[0].close()

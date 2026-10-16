"""The new-panel button lists plugin panel kinds; user_api opens them (plan 2g, task 2)."""
import pytest
from PySide6.QtWidgets import QLabel

from SciQLop.core.extensions import owned_by
from SciQLop.core.panel_kinds import PANEL_KINDS, PanelKind

from .fixtures import *  # noqa: F401,F403


def _contribute(kind_id="pk_ui.label", label="Plugin label", **fields):
    with owned_by("pk_ui"):
        PANEL_KINDS.contribute(PanelKind(kind_id, label, create=lambda n, c: QLabel(c.get("text", "")), **fields))


@pytest.fixture
def ui_kinds(main_window, qtbot):
    before = set(main_window.panels())
    yield
    PANEL_KINDS.remove_owner("pk_ui")
    for panel in [p for p in main_window.panels() if p not in before]:
        main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: set(main_window.panels()) <= before)


@pytest.fixture
def add_button(main_window, qtbot, ui_kinds):
    panel = main_window.new_plot_panel()
    area = main_window._dock_of(panel).dockAreaWidget()
    qtbot.waitUntil(lambda: area.property("sciqlop_add_panel_button") is not None, timeout=1000)
    yield area.property("sciqlop_add_panel_button"), area


def _show_menu(button):
    menu = button.menu()
    menu.aboutToShow.emit()
    return menu


def test_one_kind_keeps_the_plain_button(main_window, add_button, qtbot):
    button, area = add_button
    assert button.menu() is None
    before = set(main_window.panels())
    button.click()
    qtbot.waitUntil(lambda: len(set(main_window.panels()) - before) == 1)
    opened = (set(main_window.panels()) - before).pop()
    assert main_window._dock_of(opened).dockAreaWidget() is area


def test_a_plugin_kind_adds_a_menu(main_window, add_button, qtbot):
    button, area = add_button
    _contribute()
    qtbot.waitUntil(lambda: button.menu() is not None)
    menu = _show_menu(button)
    assert [a.text() for a in menu.actions()] == ["Panel", "Plugin label"]
    before = set(main_window.panels())
    menu.actions()[1].trigger()
    qtbot.waitUntil(lambda: len(set(main_window.panels()) - before) == 1)
    opened = (set(main_window.panels()) - before).pop()
    assert isinstance(opened, QLabel)
    assert main_window._dock_of(opened).dockAreaWidget() is area


def test_withdrawing_the_kind_removes_the_menu(add_button, qtbot):
    button, _ = add_button
    _contribute()
    qtbot.waitUntil(lambda: button.menu() is not None)
    PANEL_KINDS.remove_owner("pk_ui")
    qtbot.waitUntil(lambda: button.menu() is None)


def test_hidden_kind_is_not_listed(add_button, qtbot):
    button, _ = add_button
    _contribute("pk_ui.hidden", "Hidden", in_new_menu=False)
    _contribute()
    qtbot.waitUntil(lambda: button.menu() is not None)
    assert [a.text() for a in _show_menu(button).actions()] == ["Panel", "Plugin label"]


def test_user_api_open_panel(main_window, ui_kinds):
    from SciQLop.user_api.panels import open_panel, list_panel_kinds
    from SciQLop.user_api.plot import PlotPanel
    _contribute()
    panel = open_panel("sciqlop.time_panel")
    assert isinstance(panel, PlotPanel)
    widget = open_panel("pk_ui.label", text="x")
    assert isinstance(widget, QLabel) and widget.text() == "x"
    assert {"sciqlop.time_panel", "pk_ui.label"} <= set(list_panel_kinds())

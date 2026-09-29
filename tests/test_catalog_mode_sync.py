"""The catalog interaction mode has two controls: the chrome-row combo and the
right-click menu's Mode submenu. Changing either must show in the other."""
import pytest

from SciQLop.core import TimeRange


@pytest.fixture
def container(qtbot):
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel(name="ModeSync", time_range=TimeRange(1_000_000.0, 1_086_400.0))
    c = PanelContainer(panel)
    qtbot.addWidget(c)
    return c


_menus = []  # a QMenu's actions die with it; keep each built menu alive


def _menu_mode_actions(panel):
    from PySide6.QtWidgets import QMenu
    menu = QMenu()
    _menus.append(menu)
    panel.catalog_manager.build_catalogs_menu(menu)
    submenus = [a.menu() for a in menu.actions() if a.menu() is not None]
    nested = [a.menu() for m in submenus for a in m.actions() if a.menu() is not None]
    mode_menu = next(m for m in submenus + nested if m.title().startswith("Mode"))
    return {a.text().lower(): a for a in mode_menu.actions()}


def _checked_menu_mode(panel):
    return next(name for name, a in _menu_mode_actions(panel).items() if a.isChecked())


def test_chrome_combo_change_reaches_the_menu(container):
    chrome = container.catalog_chrome
    combo = chrome._mode_combo
    combo.setCurrentIndex(combo.findData("edit"))
    assert container.panel.catalog_manager.mode.value == "edit"
    assert _checked_menu_mode(container.panel) == "edit"


def test_mode_shortcut_reaches_the_menu(container):
    container.catalog_chrome.cycle_mode()
    assert _checked_menu_mode(container.panel) == container.catalog_chrome.mode


def test_menu_change_reaches_the_chrome_combo(container):
    _menu_mode_actions(container.panel)["jump"].trigger()
    assert container.catalog_chrome.mode == "jump"

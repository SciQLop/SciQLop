"""The menu bar holds what a new user looks for: File, a real Help, and no
developer tools in the way."""
from .fixtures import *
from PySide6.QtGui import QAction, QKeySequence


def _texts(menu):
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def _action(menu, text) -> QAction:
    return next(a for a in menu.actions() if a.text() == text)


def test_the_menu_bar_starts_with_file_and_ends_with_help(main_window):
    titles = [a.text() for a in main_window.menuBar().actions()]
    assert titles[0] == "File" and titles[-1] == "Help"


def test_file_menu_entries(main_window):
    assert _texts(main_window.fileMenu) == ["New plot panel", "Switch workspace…", "Quit"]
    assert _action(main_window.fileMenu, "New plot panel").shortcut() == QKeySequence("Ctrl+N")
    assert _action(main_window.fileMenu, "Quit").shortcut() == QKeySequence("Ctrl+Q")
    assert _action(main_window.fileMenu, "Quit").menuRole() == QAction.MenuRole.QuitRole


def test_file_new_plot_panel_adds_a_panel(main_window):
    before = len(main_window.plot_panels())
    _action(main_window.fileMenu, "New plot panel").trigger()
    assert len(main_window.plot_panels()) == before + 1


def test_file_switch_workspace_shows_the_welcome_page(main_window):
    welcome = main_window.dock_manager.findDockWidget("Welcome")
    welcome.toggleView(False)
    _action(main_window.fileMenu, "Switch workspace…").trigger()
    assert not welcome.isClosed()


def test_file_quit_closes_the_window(main_window, monkeypatch):
    closed = []
    monkeypatch.setattr(main_window, "close", lambda: closed.append(True))
    _action(main_window.fileMenu, "Quit").trigger()
    assert closed == [True]


def test_help_menu_entries(main_window):
    assert _texts(main_window.helpMenu) == [
        "Documentation and tutorials", "Take a tour…", "Keyboard shortcuts",
        "Report a problem…", "Troubleshooting", "About SciQLop"]


def test_help_links_open_in_the_browser(main_window, monkeypatch):
    opened = []
    monkeypatch.setattr("PySide6.QtGui.QDesktopServices.openUrl", lambda url: opened.append(url.toString()))
    _action(main_window.helpMenu, "Documentation and tutorials").trigger()
    _action(main_window.helpMenu, "Report a problem…").trigger()
    assert opened == ["https://sciqlop.github.io", "https://github.com/SciQLop/SciQLop/issues/new"]


def test_about_shows_the_version(main_window):
    import SciQLop
    from SciQLop.core.ui.main_menus import about_text
    assert SciQLop.__version__ in about_text()


def test_developer_tools_are_under_troubleshooting(main_window):
    troubleshooting = _action(main_window.helpMenu, "Troubleshooting").menu()
    assert _texts(troubleshooting) == ["Profiling", "Reload theme"]
    assert "Profiling" not in _texts(main_window.toolsMenu)
    assert "Reload theme" not in _texts(main_window.viewMenu)


def test_the_welcome_page_offers_plotting_before_jupyterlab(main_window, qapp):
    names = list(qapp.quickstart_shortcuts)
    assert names[0] == "New plot panel"
    assert "AMDA" in qapp.quickstart_shortcut("New plot panel")["description"]

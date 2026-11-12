"""The File and Help menus of the main window."""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QMenu, QMessageBox

import SciQLop
from SciQLop.components.crash_report.backend import ISSUES_URL
from SciQLop.components.shortcuts import bind_shortcut, bind_tooltip
from SciQLop.core.ui.tooltips import rich_tooltip

DOCUMENTATION_URL = "https://sciqlop.github.io"


def about_text() -> str:
    return (f"<b>SciQLop {SciQLop.__version__}</b><br><br>"
            "Interactive visualization and labeling of in-situ space plasma time series.<br><br>"
            f'<a href="{DOCUMENTATION_URL}">{DOCUMENTATION_URL}</a><br>'
            f'<a href="{SciQLop.__url__}">{SciQLop.__url__}</a>')


def _add(menu: QMenu, text: str, slot, title: str, body: str) -> QAction:
    action = menu.addAction(text, slot)
    action.setToolTip(rich_tooltip(title, body))
    return action


def _open(url: str):
    return lambda: QDesktopServices.openUrl(QUrl(url))


def _new_menu(title: str) -> QMenu:
    menu = QMenu(title)
    menu.setToolTipsVisible(True)
    return menu


def show_about(window) -> None:
    QMessageBox.about(window, "About SciQLop", about_text())


# Slots are the window's own methods, never lambdas that capture it: these
# menus have no Qt parent, so such a lambda would keep the window alive.
def build_file_menu(window) -> QMenu:
    menu = _new_menu("File")
    menu.addAction(window.addTSPanel)
    _add(menu, "Switch workspace…", window.show_welcome_page,
         "Switch workspace", "Show the welcome page, where workspaces are opened and created.")
    menu.addSeparator()
    quit_action = _add(menu, "Quit", window.quit, "Quit", "Close SciQLop.")
    quit_action.setMenuRole(QAction.MenuRole.QuitRole)
    bind_shortcut(quit_action, "app.quit")
    bind_tooltip(quit_action, "app.quit", "Quit", "Close SciQLop.")
    return menu


def _troubleshooting_menu(window) -> QMenu:
    """Tools a user only needs when asked to by someone investigating a problem."""
    menu = _new_menu("Troubleshooting")
    menu.addMenu(window.profiling_menu)
    _add(menu, "Reload theme", window.reload_theme,
         "Reload theme", "Re-apply the current color palette and refresh all icons.")
    return menu


def build_help_menu(window) -> QMenu:
    menu = _new_menu("Help")
    _add(menu, "Documentation and tutorials", _open(DOCUMENTATION_URL),
         "Documentation and tutorials", "Open the SciQLop website in your browser.")
    _add(menu, "Guides", window.show_guides,
         "Guides", "Short animations that each show one manipulation: plotting, catalogs, events.")
    _add(menu, "Take a tour…", window.open_tour_picker,
         "Take a tour", "Pick a guided walkthrough of a SciQLop feature.")
    window.shortcutsHelpAction = menu.addAction("Keyboard shortcuts", window.show_shortcuts_help)
    bind_shortcut(window.shortcutsHelpAction, "app.shortcuts_help")
    bind_tooltip(window.shortcutsHelpAction, "app.shortcuts_help",
                 "Keyboard shortcuts", "List every keyboard shortcut.")
    menu.addSeparator()
    _add(menu, "Report a problem…", _open(ISSUES_URL),
         "Report a problem", "Open a new issue on GitHub in your browser.")
    window.troubleshootingMenu = _troubleshooting_menu(window)
    menu.addMenu(window.troubleshootingMenu)
    menu.addSeparator()
    about = _add(menu, "About SciQLop", window.show_about, "About SciQLop", "Version and links.")
    about.setMenuRole(QAction.MenuRole.AboutRole)
    return menu

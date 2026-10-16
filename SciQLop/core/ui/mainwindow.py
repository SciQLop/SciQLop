import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Union, List, Tuple

import humanize
import psutil

import PySide6QtAds as QtAds
import shiboken6
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QWidget, QMenu, QMessageBox

from SciQLop.components.workspaces import workspaces_manager_instance
from SciQLop.components.sciqlop_logging.logs_widget import LogsWidget
from SciQLopPlots import PropertiesPanel, ProductsView, Icons
from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
from SciQLop.components.plotting.ui.panel_container import PanelContainer
from SciQLop.components.welcome import WelcomePage
from SciQLop.core import TimeRange
from SciQLop.core.sciqlop_application import sciqlop_app
from SciQLop.core.unique_names import auto_name, claim_name, release_name
from SciQLop.components.workspaces import Workspace
from SciQLop.components.theming import register_icon, get_icon, get_current_style_icon, theme_icon, theme_adapted_icon, SciQLopStyle, qtads_stylesheet
from SciQLop.core.ui import Metrics
from SciQLop.core.ui.tooltips import rich_tooltip
from SciQLop.components.command_palette.menu_entries import add_menu_entries
from SciQLop.core.menus import MAIN_TOOLS
from SciQLop.core.docks import DOCKS, Dock, _ExistingWidget
from SciQLop.core.extensions import current_owner, owned_by
from SciQLop.core.panel_kinds import KIND_PROPERTY, PANEL_KINDS, PanelKind
from SciQLop.core.plot_kinds import TIME_PANEL
from SciQLop.core.ui.panel_host import dock_panel, panel_docks, panel_of
import SciQLop.components.plotting.time_panel_kind  # noqa: F401  a main window always has the core panel kind
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.kernel_namespace import contribute_name
from SciQLopPlots import SciQLopMultiPlotPanel
from SciQLop.components.settings.ui import SettingsPanel
from SciQLop.components.shortcuts import bind_shortcut, bind_tooltip
from SciQLop.components.shortcuts.ui import ShortcutsHelp
from SciQLop.components.catalogs.ui import CatalogBrowser
from SciQLop.components.onboarding.backend.settings import OnboardingSettings
from SciQLop.components.onboarding.ui.tour_controller import run_tour

__here__ = os.path.dirname(__file__)

register_icon("plot_panel", QtGui.QIcon("://icons/plot_panel_128.png"))

log = getLogger(__name__)

_DOCK_VIEW_TOOLTIPS = {
    "Welcome": "Workspaces, examples and templates.",
    "Products": "Browse every data archive by mission and instrument. Drag a product onto a panel to plot it.",
    "Catalogs": "Lists of time intervals (events) you can overlay on plots and edit.",
    "Logs": "Application log messages, useful when something fails.",
    "Settings": "Themes, plot defaults, plugins and workspaces.",
    "Properties": "Inspect and style the selected plot or curve.",
    "Toolbar": "Quick-access buttons for common plotting actions.",
    "SciQLop JupyterLab": "A notebook interface connected to the same Python session as SciQLop.",
    "Plugin Store": "Browse and install community plugins.",
    "Agents": "Chat with an AI assistant that can inspect this session.",
}


def _dock_view_tooltip(title: str) -> Optional[str]:
    body = _DOCK_VIEW_TOOLTIPS.get(title)
    return rich_tooltip(title, body) if body else None


def _apply_dock_view_tooltip(doc: QtAds.CDockWidget, action: QtGui.QAction) -> None:
    tooltip = _dock_view_tooltip(doc.windowTitle())
    if tooltip is None:
        return
    action.setToolTip(tooltip)
    doc.tabWidget().setToolTip(tooltip)
    if doc.isAutoHide():
        doc.sideTabWidget().setToolTip(tooltip)
        _show_side_tab_tooltip_when_hover_opens(doc)


def _cursor_over(widget: QWidget) -> bool:
    return widget.rect().contains(widget.mapFromGlobal(QtGui.QCursor.pos()))


def _show_side_tab_tooltip_when_hover_opens(doc: QtAds.CDockWidget) -> None:
    """QtAds opens a hovered auto-hide panel with a synthetic mouse press
    500 ms in, and Qt drops the pending tooltip (700 ms) on any press, so
    a side tab's tooltip only ever showed when its panel was already open."""
    def _on_visibility(visible: bool) -> None:
        tab = doc.sideTabWidget()
        if visible and tab is not None and _cursor_over(tab):
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), tab.toolTip(), tab)
    doc.visibilityChanged.connect(_on_visibility)


def _extract_panel(dock_widget):
    # dock_widget itself can be a dead Shiboken wrapper (e.g. queried from
    # the dock manager during teardown) -- same class of hazard as the
    # w.panel check below, just one level up.
    if dock_widget is None or not shiboken6.isValid(dock_widget):
        return None
    w = dock_widget.widget()
    if isinstance(w, PanelContainer):
        # the panel can die without going through remove_panel (e.g. user code
        # deleteLater'd it) — a dead Shiboken wrapper must not break the whole
        # panel enumeration
        return w.panel if shiboken6.isValid(w.panel) else None
    if isinstance(w, SciQLopMultiPlotPanel):
        return w if shiboken6.isValid(w) else None
    return None


def _follow_panel_renames(panel, dock_widget: QtAds.CDockWidget) -> None:
    """The Properties inspector renames a panel with setObjectName (#152). QtAds keys
    docks by the name they were added with and never re-keys them, so the dock keeps
    that name as an internal id; only its title follows the panel's name. A taken or
    empty name is replaced, and setObjectName shows the replacement in the inspector."""
    def _on_renamed(new_name: str) -> None:
        old_name = dock_widget.windowTitle() if shiboken6.isValid(dock_widget) else new_name
        if new_name == old_name:
            return
        release_name(old_name)
        unique = claim_name(new_name or old_name)
        dock_widget.setWindowTitle(unique)
        if unique != new_name:
            panel.setObjectName(unique)
    panel.objectNameChanged.connect(_on_renamed)


def _destroy_content_before_its_window(dock_widget: QtAds.CDockWidget) -> None:
    """A force-closed dock (closeDockWidget(), skipping remove_panel) still holds its panel
    when `closed` fires, and QtAds has already queued the deletion of its floating window.
    Destroying the panel now, while that window and its QRhi are alive, keeps Qt's
    QRhiWidget from touching the freed QRhi (docs/qt-bugs/qrhiwidget_reparent_uaf.py)."""
    content = dock_widget.widget()
    if content is not None and shiboken6.isValid(content):
        shiboken6.delete(content)


_SIDE_BAR = QtAds.PySide6QtAds.ads.SideBarLocation
_SIDE_BARS = {"left": _SIDE_BAR.SideBarLeft, "right": _SIDE_BAR.SideBarRight, "bottom": _SIDE_BAR.SideBarBottom}
# simplify: no caller docks on the top side bar, so it maps to "bottom"; add a "top" placement if one does.
_PLACEMENT_OF_SIDE_BAR = {_SIDE_BAR.SideBarLeft: "left", _SIDE_BAR.SideBarRight: "right",
                          _SIDE_BAR.SideBarBottom: "bottom", _SIDE_BAR.SideBarTop: "bottom"}


def _dock_icon(icon: Optional[str], widget: QWidget) -> QIcon:
    if icon is None:
        return widget.windowIcon()
    return QIcon(icon) if os.path.exists(icon) else get_icon(icon)


def _queue_content_delete(dock_widget: QtAds.CDockWidget) -> None:
    """Call before closeDockWidget(): the content's deferred delete is then posted before
    QtAds' deletion of a floating dock's window, so the content dies while that window and
    its QRhi are alive; taken out of that window later, Qt's QRhiWidget would keep a QRhi
    freed with it (docs/qt-bugs/qrhiwidget_reparent_uaf.py). Not deleted right away: a
    withdrawal can come from a signal of a widget inside the content."""
    content = dock_widget.takeWidget()
    if content is not None:
        content.hide()
        content.deleteLater()


def _build_dock_content(dock: Dock) -> Optional[QWidget]:
    try:
        widget = dock.build()
    except Exception:
        log.error(f"dock {dock.id} failed to build", exc_info=True)
        return None
    if not isinstance(widget, QWidget):
        log.error(f"dock {dock.id}: build() returned {type(widget).__name__}, not a QWidget")
        return None
    return widget


def _create_panel(kind: PanelKind, name: str, config: dict) -> QWidget:
    try:
        widget = kind.create(name, config)
    except Exception:
        log.error(f"panel kind {kind.id} failed to create {name!r}", exc_info=True)
        raise
    if not isinstance(widget, QWidget):
        log.error(f"panel kind {kind.id}: create() returned {type(widget).__name__}, not a QWidget")
        raise TypeError(f"panel kind {kind.id}: create() must return a QWidget, got {type(widget).__name__}")
    return widget


def _name_panel(widget: QWidget, name: str, icon: Optional[str]) -> None:
    widget.setObjectName(name)
    widget.setWindowTitle(name)
    if icon is not None:
        widget.setWindowIcon(_dock_icon(icon, widget))


def _new_dock_widget(dock: Dock, widget: QWidget) -> QtAds.CDockWidget:
    dock_widget = QtAds.CDockWidget(dock.title)
    if dock.placement == "center":
        dock_widget.setWidget(widget)
    else:
        dock_widget.setWidget(widget, QtAds.CDockWidget.ForceNoScrollArea)
    dock_widget.setMinimumSizeHintMode(QtAds.CDockWidget.MinimumSizeHintFromContent)
    icon = _dock_icon(dock.icon, widget)
    if not icon.isNull():
        dock_widget.setIcon(icon)
    return dock_widget


def _surface(size: QtCore.QSize):
    return size.width() * size.height()


def _confirm_close_with_running_jobs(parent, event, jobs: list) -> bool:
    """Warn if any job is still running. Returns True if the close was
    cancelled (event.ignore() already called)."""
    running = [j for j in jobs if j.get("status") == "running"]
    if not running:
        return False
    names = ", ".join(j["name"] for j in running)
    reply = QMessageBox.question(
        parent, "Jobs still running",
        f"{len(running)} job(s) are still running and will continue in the "
        f"background: {names}. Close anyway?",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if reply == QMessageBox.No:
        event.ignore()
        return True
    return False


def _dirty_catalog_names() -> List[str]:
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    from SciQLop.components.catalogs.backend.provider import Capability
    from SciQLop.components.sciqlop_logging import getLogger
    try:
        providers = CatalogRegistry.instance().providers()
    except Exception:
        return []
    dirty = []
    for p in providers:
        try:
            if Capability.SAVE in p.capabilities() and p.is_dirty():
                dirty.append(p.name)
        except Exception:
            getLogger(__name__).warning(
                "Could not check dirty state of provider %r", p, exc_info=True)
    return dirty


def _confirm_close_with_dirty_catalogs(parent, event, dirty_providers: list) -> bool:
    """Warn if any catalog provider has unsaved changes. Returns True if the
    close was cancelled (event.ignore() already called)."""
    if not dirty_providers:
        return False
    names = ", ".join(dirty_providers)
    reply = QMessageBox.question(
        parent, "Unsaved catalog changes",
        f"The following catalog source(s) have unsaved changes that will be "
        f"lost: {names}. Close anyway?",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if reply == QMessageBox.No:
        event.ignore()
        return True
    return False


class SciQLopMainWindow(QtWidgets.QMainWindow):
    AUTO_HIDE_TAB_ICON = 2.2  # em — side bar tab icon, set here because
    # qproperty-iconSize does not survive a theme change (see _apply_dock_theme)
    workspace: Workspace = None
    panels_list_changed = QtCore.Signal(list)
    panel_added = QtCore.Signal(QWidget)

    def __init__(self):

        QtWidgets.QMainWindow.__init__(self)
        self.setObjectName("SciQLopMainWindow")
        self._initial_geometry_applied = False
        self._setup_ui()
        sciqlop_app().panels_list_changed.connect(self.panels_list_changed)
        sciqlop_app().main_window = self

    def _setup_ui(self):
        self._setup_dock_manager()
        self._setup_menus()

        self._default_time_range = TimeRange(
            (datetime.utcnow() - timedelta(days=361)).timestamp(),
            (datetime.utcnow() - timedelta(days=360)).timestamp())

        self.welcome = WelcomePage()
        self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, self.welcome)

        self.setWindowTitle("SciQLop")
        self.follow_docks()
        with owned_by("sciqlop"):
            self._setup_side_panels()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_command_palette()

        self._appstore = None
        store = self.toolsMenu.addAction("Plugin Store", self._show_appstore)
        store.setToolTip(rich_tooltip(
            "Plugin Store",
            "Browse and install community plugins."))
        self.welcome.backend.appstore_requested.connect(self._show_appstore)
        self.welcome.backend.appstore_updates_requested.connect(self._show_appstore_updates)

    def showEvent(self, event):
        super().showEvent(event)
        # Apply the initial geometry on first show — running this from __init__
        # is unreliable on macOS: setGeometry() before the native NSWindow
        # exists is silently ignored and the window comes up at Qt's default
        # ~640×480 (which looks like ~1/4 of a Retina screen). showEvent fires
        # AFTER the platform window is created so the geometry actually sticks.
        if not self._initial_geometry_applied:
            self._initial_geometry_applied = True
            self._center_and_maximise_on_screen()

    def _setup_dock_manager(self):
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FocusHighlighting, True)
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FloatingContainerHasWidgetIcon, True)
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.TabCloseButtonIsToolButton, True)
        QtAds.CDockManager.setAutoHideConfigFlags(
            QtAds.CDockManager.AutoHideFeatureEnabled |
            QtAds.CDockManager.AutoHideCloseButtonCollapsesDock |
            QtAds.CDockManager.AutoHideHasMinimizeButton |
            QtAds.CDockManager.AutoHideShowOnMouseOver |
            QtAds.CDockManager.AutoHideOpenOnDragHover |
            QtAds.CDockManager.AutoHideSideBarsIconOnly
        )
        if "WAYLAND_DISPLAY" in os.environ:
            QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FloatingContainerForceQWidgetTitleBar, True)
        self.dock_manager = QtAds.CDockManager(self)
        self.dock_manager.dockAreaCreated.connect(self._on_dock_area_created)
        self.dock_manager.focusedDockWidgetChanged.connect(self._on_focused_dock_widget_changed)
        self._focused_autohide_widget: Optional[QtAds.CDockWidget] = None
        self._autohide_focus_order: List[QtAds.CDockWidget] = []
        self._apply_dock_theme()
        sciqlop_app().theme_changed.connect(self._schedule_dock_theme)

    def _schedule_dock_theme(self, _palette_name: str = ""):
        # QApplication.setPalette() *posts* the repolish, so it lands after this
        # signal. Re-asserting now would just be undone; wait for the queue.
        QtCore.QTimer.singleShot(0, self._apply_dock_theme)

    def _apply_dock_theme(self):
        """Re-assert everything QApplication.setPalette() takes away from QtAds.

        A theme change repolishes every widget, after which QtAds widgets ignore
        the application stylesheet permanently and buttons lose the sizes it gave
        them. Only a fresh widget-level assignment gets through, so both the sheet
        and the icon size have to be set again here on every theme change.
        """
        app = sciqlop_app()
        self.dock_manager.setStyleSheet(qtads_stylesheet(app.palette(), app.current_theme()))
        for tab in self._auto_hide_tabs():
            tab.setIconSize(Metrics.icon_size(self.AUTO_HIDE_TAB_ICON))

    def _auto_hide_tabs(self):
        for dock_widget in self.dock_manager.dockWidgetsMap().values():
            container = dock_widget.autoHideDockContainer()
            if container is not None:
                yield container.autoHideTab()

    def _on_focused_dock_widget_changed(self, old, now):
        """QtAds' FocusHighlighting tags the docked widget's own inner tab with
        `focused`, not its side-bar icon — mirror it there so the panel that is
        "on top" among several simultaneously-open ones gets its own cue."""
        for dock_widget, is_focused in ((old, False), (now, True)):
            if dock_widget is None:
                continue
            container = dock_widget.autoHideDockContainer()
            if container is None:
                continue
            tab = container.autoHideTab()
            tab.setProperty("focused", is_focused)
            tab.style().unpolish(tab)
            tab.style().polish(tab)
            if is_focused:
                self._focused_autohide_widget = dock_widget
                if dock_widget in self._autohide_focus_order:
                    self._autohide_focus_order.remove(dock_widget)
                self._autohide_focus_order.append(dock_widget)
            elif self._focused_autohide_widget is dock_widget:
                self._focused_autohide_widget = None

    def _track_autohide_widget_focus(self, dock_widget):
        """QtAds only ever assigns focus when an auto-hide panel is *opened*
        (AutoHideDockContainer::collapseView(false) calls setDockWidgetFocused);
        collapsing/hiding the focused one leaves it focused, so nothing else
        ever gets the "on top" cue again once it is. Pick a new one ourselves."""
        dock_widget.visibilityChanged.connect(
            lambda visible, dw=dock_widget: self._on_autohide_widget_visibility_changed(dw, visible))

    def _on_autohide_widget_visibility_changed(self, dock_widget, visible):
        if visible:
            return
        if dock_widget in self._autohide_focus_order:
            self._autohide_focus_order.remove(dock_widget)
        if self._focused_autohide_widget is not dock_widget:
            return
        self._focused_autohide_widget = None
        candidate = self._next_autohide_focus_candidate()
        if candidate is not None:
            self.dock_manager.setDockWidgetFocused(candidate)

    def _next_autohide_focus_candidate(self) -> Optional[QtAds.CDockWidget]:
        while self._autohide_focus_order:
            candidate = self._autohide_focus_order[-1]
            if shiboken6.isValid(candidate) and candidate.isVisible():
                return candidate
            self._autohide_focus_order.pop()
        for dock_widget in self.dock_manager.dockWidgetsMap().values():
            if (shiboken6.isValid(dock_widget) and dock_widget.isVisible()
                    and dock_widget.autoHideDockContainer() is not None):
                return dock_widget
        return None

    def _setup_menus(self):
        self._menubar = QtWidgets.QMenuBar(self)
        self.setMenuBar(self._menubar)
        self._menubar.setGeometry(QtCore.QRect(0, 0, 615, 23))
        self._menubar.setDefaultUp(True)

        self.viewMenu = QMenu("View")
        self.viewMenu.setToolTipsVisible(True)
        self._menubar.addMenu(self.viewMenu)
        reload_theme = self.viewMenu.addAction(
            "Reload theme",
            lambda: sciqlop_app().apply_theme(SciQLopStyle().color_palette))
        reload_theme.setToolTip(rich_tooltip(
            "Reload theme",
            "Re-apply the current color palette and refresh all icons."))

        self.fullScreenAction = self.viewMenu.addAction("Full screen")
        self.fullScreenAction.setCheckable(True)
        bind_shortcut(self.fullScreenAction, "app.full_screen")
        self.fullScreenAction.toggled.connect(self._set_full_screen)
        bind_tooltip(self.fullScreenAction, "app.full_screen",
                     "Full screen", "Show SciQLop without window decorations.")

        self.toolsMenu = QMenu("Tools")
        self.toolsMenu.setToolTipsVisible(True)
        self._menubar.addMenu(self.toolsMenu)
        self._tools_entry_actions = []
        self.toolsMenu.aboutToShow.connect(self._refresh_tools_entries)
        open_lab = self.toolsMenu.addAction(
            "Open JupyterLab", self.open_jupyterlab_widget)
        open_lab.setToolTip(rich_tooltip(
            "Open JupyterLab",
            "Open the embedded JupyterLab connected to"
            " this session's kernel."))

        from SciQLop.components.profiling import ProfilingMenu
        self._profiling_menu = ProfilingMenu(self)
        self.toolsMenu.addMenu(self._profiling_menu.menu)

        take_a_tour = self.toolsMenu.addAction(
            "Take a tour…", self._open_tour_picker)
        take_a_tour.setToolTip(rich_tooltip(
            "Take a tour",
            "Pick a guided walkthrough of a SciQLop feature."))

        self.helpMenu = QMenu("Help")
        self.helpMenu.setToolTipsVisible(True)
        self._menubar.addMenu(self.helpMenu)
        self._shortcuts_help = None
        self.shortcutsHelpAction = self.helpMenu.addAction(
            "Keyboard shortcuts", self.show_shortcuts_help)
        bind_shortcut(self.shortcutsHelpAction, "app.shortcuts_help")
        bind_tooltip(self.shortcutsHelpAction, "app.shortcuts_help",
                     "Keyboard shortcuts", "List every keyboard shortcut.")
        self._create_toolbar()

    def _create_toolbar(self):
        """Created with the menus, before follow_docks() replays docks that put their toggle on it."""
        self.toolBar = QtWidgets.QToolBar(self)
        self.toolBar.setWindowTitle("Toolbar")
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, self.toolBar)
        self.toolBar.setVisible(False)

    def show_shortcuts_help(self):
        if self._shortcuts_help is None:
            self._shortcuts_help = ShortcutsHelp(self)
        self._shortcuts_help.show()
        self._shortcuts_help.raise_()
        self._shortcuts_help.activateWindow()

    def _setup_side_panels(self):
        self.productTree = ProductsView(self)
        self.productTree.setWindowTitle("Products")
        self.productTree.setWindowIcon(theme_icon("tree"))
        self.add_side_pan(self.productTree)

        from SciQLop.components.products.product_context_menu import setup_product_context_menu
        setup_product_context_menu(self.productTree, self)

        from SciQLop.components.products.sidebar_smart_search import setup_sidebar_smart_search
        setup_sidebar_smart_search(self.productTree)

        self.catalogs_browser = CatalogBrowser(self)
        self.catalogs_browser.setWindowIcon(theme_icon("catalogue"))
        self.add_side_pan(self.catalogs_browser)
        self.panel_added.connect(self.catalogs_browser.connect_to_panel)

        wm = workspaces_manager_instance()
        contribute_name("sciqlop.main_window", "main_window", wm.wrap_qt(self))
        wm.workspace_loaded.connect(self._show_workspace_name_in_title)
        from SciQLop.components.onboarding.backend.registry import register_builtin_tours
        register_builtin_tours()
        self._onboarding_controller = None
        self._tour_picker = None
        self._tour_timer = QtCore.QTimer(self)
        self._tour_timer.setSingleShot(True)
        self._tour_timer.setInterval(500)
        self._tour_timer.timeout.connect(self._start_getting_started_tour)
        wm.workspace_loaded.connect(self._maybe_run_onboarding_tour)
        if wm.has_workspace:
            self._on_workspace_already_loaded(wm.workspace)
        sciqlop_app().add_quickstart_shortcut("JupyterLab", "Open JupyterLab",
                                              Icons.get_icon("Jupyter"),
                                              self.open_jupyterlab_widget)
        open_browser = QtGui.QAction("Open JupyterLab in browser", self.toolsMenu)
        open_browser.triggered.connect(wm.open_in_browser)
        self.toolsMenu.insertAction(self._profiling_menu.menu.menuAction(), open_browser)
        open_browser.setToolTip(rich_tooltip(
            "Open JupyterLab in browser",
            "Open the JupyterLab server in your default web browser."))

        self.logs = LogsWidget(self)
        self.logs.setWindowIcon(theme_icon("view_list"))
        logs = self.viewMenu.addAction("Logs", self._show_logs)
        logs.setToolTip(rich_tooltip(
            "Logs", "Show the application log panel."))

        self.settings_panel = SettingsPanel(self)
        self.settings_panel.setWindowIcon(theme_adapted_icon("settings"))
        self.settings_panel.setWindowTitle("Settings")
        self.add_side_pan(self.settings_panel)

        self.properties_panel = PropertiesPanel(self)
        self.properties_panel.setWindowTitle("Properties")
        self.properties_panel.setWindowIcon(theme_adapted_icon("plot_properties"))
        self.add_side_pan(self.properties_panel)
        from SciQLop.components.plotting.ui.graph_context_inspector import (
            install_inspector_tree_tooltips,
        )
        install_inspector_tree_tooltips(self.properties_panel)


    def _setup_toolbar(self):
        self.setWindowIcon(QtGui.QIcon("://icons/SciQLop.png"))
        toolbar_toggle = self.toolBar.toggleViewAction()
        self.viewMenu.addAction(toolbar_toggle)
        toolbar_tooltip = _dock_view_tooltip("Toolbar")
        if toolbar_tooltip:
            toolbar_toggle.setToolTip(toolbar_tooltip)

        self.addTSPanel = QtGui.QAction(self)
        self.addTSPanel.setIcon(theme_icon("add_graph"))
        self.addTSPanel.setText("New plot panel")
        self.addTSPanel.setToolTip(rich_tooltip(
            "New plot panel",
            "Create an empty panel to drop products onto."))
        self.addTSPanel.triggered.connect(lambda: self.new_plot_panel())
        self.toolBar.addAction(self.addTSPanel)
        sciqlop_app().add_quickstart_shortcut(name="New plot panel", description="Add a new plot panel",
                                              icon=theme_icon("add_graph"), callback=self.new_plot_panel)
        sciqlop_app().add_quickstart_shortcut(
            name="Take a tour", description="Pick a guided walkthrough of a SciQLop feature",
            icon=theme_icon("assistant"), callback=self._open_tour_picker)

    def _setup_status_bar(self):
        self._statusbar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self._statusbar)
        self._statusbar.setFixedHeight(Metrics.ex(1.5))

        self._mem_usage = QtWidgets.QProgressBar()
        self._sys_mem = psutil.virtual_memory().total // 1024 ** 2
        self._mem_usage.setMaximum(self._sys_mem)
        self._mem_usage.setFormat(f"System memory usage: %v / {self._sys_mem:.2f} MB")
        self._mem_usage.setToolTip(rich_tooltip(
            "Memory usage",
            "Memory used by SciQLop out of system memory."))

        self._cpu_usage = QtWidgets.QProgressBar()
        self._cpu_usage.setFormat("CPU usage: %v%")
        self._cpu_usage.setToolTip(rich_tooltip(
            "CPU usage",
            "CPU used by SciQLop."))

        self._network_usage_send_speed = QtWidgets.QLabel()
        self._network_usage_bytes_sent = psutil.net_io_counters().bytes_sent
        self._network_usage_recv_speed = QtWidgets.QLabel()
        self._network_usage_bytes_recv = psutil.net_io_counters().bytes_recv

        self._stats_container = QtWidgets.QWidget()
        stats_layout = QtWidgets.QHBoxLayout(self._stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(8)
        stats_layout.addWidget(self._network_usage_recv_speed)
        stats_layout.addWidget(self._network_usage_send_speed)
        stats_layout.addWidget(self._cpu_usage)
        stats_layout.addWidget(self._mem_usage)
        self._stats_container.setVisible(False)

        self._stats_toggle = QtWidgets.QToolButton()
        self._stats_toggle.setText("\u25B6")
        self._stats_toggle.setToolTip(rich_tooltip(
            "System stats",
            "Show live CPU, memory, and network usage."))
        self._stats_toggle.setAutoRaise(True)
        self._stats_toggle.setFixedSize(Metrics.icon_size(1.5))
        self._stats_toggle.clicked.connect(self._toggle_stats)

        self._statusbar.addPermanentWidget(self._stats_toggle)
        self._statusbar.addPermanentWidget(self._stats_container)

        self.catalogs_browser.provider_error.connect(
            lambda msg: self._statusbar.showMessage(msg, 8000))

        self._refresh_mem_timer = QtCore.QTimer(self)
        self._refresh_mem_timer.timeout.connect(self._update_usage)
        self._refresh_mem_timer.start(1000)

    def _toggle_stats(self):
        visible = not self._stats_container.isVisible()
        self._stats_container.setVisible(visible)
        self._stats_toggle.setText("\u25C0" if visible else "\u25B6")
        self._stats_toggle.setToolTip(rich_tooltip(
            "System stats",
            "Hide live usage stats."
            if visible else
            "Show live CPU, memory, and network usage."))

    def _setup_command_palette(self):
        from SciQLop.components.command_palette.ui.palette_widget import CommandPalette
        from SciQLop.components.command_palette.backend.history import LRUHistory
        from SciQLop.components.command_palette.settings import CommandPaletteSettings
        from SciQLop.components.settings.backend.entry import SCIQLOP_CONFIG_DIR

        palette_settings = CommandPaletteSettings()
        history_path = os.path.join(SCIQLOP_CONFIG_DIR, "command_palette_history.json")
        self._palette_history = LRUHistory(path=history_path, max_size=palette_settings.max_history_size)
        self._command_palette = CommandPalette(self, sciqlop_app().command_registry, self._palette_history)

        self.commandPaletteAction = self.viewMenu.addAction(
            "Command palette…", self._command_palette.toggle)
        bind_shortcut(self.commandPaletteAction, "app.command_palette")
        bind_tooltip(self.commandPaletteAction, "app.command_palette",
                     "Command palette", "Search and run any command, product, panel or catalog.")

    def _show_logs(self):
        dw = self.dock_manager.findDockWidget(self.logs.windowTitle())
        if dw is None:
            self.addWidgetIntoDock(QtAds.DockWidgetArea.BottomDockWidgetArea, self.logs)
        else:
            dw.toggleView(True)
            dw.raise_()

    def _show_appstore(self, name: str = ""):
        if self._appstore is None:
            from SciQLop.components.appstore import AppStorePage
            self._appstore = AppStorePage()
            self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, self._appstore)
        else:
            dw = self.dock_manager.findDockWidget(self._appstore.windowTitle())
            if dw:
                dw.toggleView(True)
                dw.raise_()
        if name:
            self._appstore.show_package(name)

    def _show_appstore_updates(self):
        self._show_appstore()
        self._appstore.show_page("updates")

    def _update_usage(self):
        self._update_cpu_usage()
        self._update_mem_usage()
        self._update_network_usage()

    def _update_cpu_usage(self):
        self._cpu_usage.setValue(psutil.cpu_percent())

    def _update_mem_usage(self):
        self._mem_usage.setValue(psutil.virtual_memory().used // 1024 ** 2)

    def _update_network_usage(self):
        self._network_usage_send_speed.setText(
            f"Network TX: {humanize.naturalsize(psutil.net_io_counters().bytes_sent - self._network_usage_bytes_sent)}/s")
        self._network_usage_recv_speed.setText(
            f"Network RX: {humanize.naturalsize(psutil.net_io_counters().bytes_recv - self._network_usage_bytes_recv)}/s")
        self._network_usage_bytes_sent = psutil.net_io_counters().bytes_sent
        self._network_usage_bytes_recv = psutil.net_io_counters().bytes_recv

    def _find_biggest_area(self) -> QtAds.CDockAreaWidget:
        biggest_area = None
        biggest_surface = 0
        for area in self.dock_manager.openedDockAreas():
            if area is not None:
                surface = _surface(area.size())
                if surface > biggest_surface and surface > 0 and area.isVisible():
                    biggest_surface = surface
                    biggest_area = area
        return biggest_area

    def _find_biggest_dock_widget(self) -> QtAds.CDockWidget:
        biggest_doc = None
        biggest_surface = 0
        for doc in self.dock_manager.openedDockWidgets():
            surface = _surface(doc.size())
            if surface > biggest_surface:
                biggest_surface = surface
                biggest_doc = doc
        return biggest_doc

    def _center_and_maximise_on_screen(self):
        frame = self.frameGeometry()
        center = sciqlop_app().primaryScreen().availableGeometry().center()
        frame.moveCenter(center)
        self.move(frame.topLeft())
        self.setGeometry(
            sciqlop_app().primaryScreen().availableGeometry().marginsRemoved(QtCore.QMargins(50, 50, 50, 50)))

    @property
    def default_range(self):
        return self._default_time_range

    def central_area(self) -> Optional[QtAds.CDockAreaWidget]:
        """Where center docks go: the biggest visible area, else the Welcome page's area."""
        area = self._find_biggest_area()
        if area is not None:
            return area
        welcome = self.dock_manager.findDockWidget("Welcome")
        return welcome.dockAreaWidget() if welcome is not None else None

    def add_side_pan(self, widget: QWidget, location=QtAds.PySide6QtAds.ads.SideBarLocation.SideBarLeft, icon=None):
        if widget is None:
            return
        owner, title = current_owner(), widget.windowTitle()
        dock_id = f"{owner}.{title}"
        self._refuse_live_duplicate(dock_id, title)
        DOCKS.contribute(Dock(id=dock_id, title=title, build=_ExistingWidget(widget, self),
                              placement=_PLACEMENT_OF_SIDE_BAR[location], icon=icon),
                         owner=owner, replace=True)

    def _refuse_live_duplicate(self, dock_id: str, title: str) -> None:
        build = DOCKS.get(dock_id).build if dock_id in DOCKS else None
        if isinstance(build, _ExistingWidget) and build.host() is self and build.alive():
            raise ValueError(f"a side pane titled {title!r} is already docked in this window")

    def follow_docks(self) -> None:
        """Place every contributed dock, now and as contributions come and go.
        Bound methods, not a receiver context (this PySide6 refuses one): each slot checks the window is alive."""
        self._docks: dict = {}
        DOCKS.signals.added.connect(self._on_dock_added)
        DOCKS.signals.removed.connect(self._on_dock_removed)
        for dock in DOCKS.list():
            self._on_dock_added(dock)

    def _places(self, dock: Dock) -> bool:
        build = dock.build
        if not isinstance(build, _ExistingWidget):
            return True
        if build.host() is not self:
            return False
        if not build.alive():
            log.debug(f"Dock {dock.id!r} is not placed: its widget was deleted")
            return False
        return True

    def _on_dock_added(self, dock: Dock) -> None:
        if not shiboken6.isValid(self) or not self._places(dock):
            return
        self._close_dock(dock.id)
        widget = _build_dock_content(dock)
        if widget is not None:
            self._docks[dock.id] = (dock, self._place_dock(dock, widget))

    def _on_dock_removed(self, dock: Dock) -> None:
        if not shiboken6.isValid(self):
            return
        placed = self._docks.get(dock.id)
        if placed is not None and placed[0] is dock:
            self._close_dock(dock.id)

    def _place_dock(self, dock: Dock, widget: QWidget) -> QtAds.CDockWidget:
        if not widget.windowTitle():
            widget.setWindowTitle(dock.title)
        dock_widget = _new_dock_widget(dock, widget)
        if dock.placement == "center":
            self._place_center_dock(dock_widget, dock.visible)
        else:
            self._place_side_pane(dock_widget, widget, _SIDE_BARS[dock.placement])
        self._add_dock_action(dock_widget, dock.toolbar)
        return dock_widget

    def _place_center_dock(self, dock_widget: QtAds.CDockWidget, visible: bool) -> None:
        area = self.central_area()
        if area is not None:
            self.dock_manager.addDockWidgetTabToArea(dock_widget, area)
        else:
            self.dock_manager.addDockWidget(QtAds.DockWidgetArea.TopDockWidgetArea, dock_widget)
        dock_widget.toggleView(visible)

    def _place_side_pane(self, dock_widget: QtAds.CDockWidget, widget: QWidget, location) -> None:
        container = self.dock_manager.addAutoHideDockWidget(location, dock_widget)
        container.autoHideTab().setIconSize(Metrics.icon_size(self.AUTO_HIDE_TAB_ICON))
        self._track_autohide_widget_focus(dock_widget)
        hint = widget.sizeHint()
        container.setSize(hint.height() if location == _SIDE_BAR.SideBarBottom else hint.width())

    def _dock_action_holders(self) -> tuple:
        return self.viewMenu, self.toolBar, self.toolsMenu

    def _add_dock_action(self, dock_widget: QtAds.CDockWidget, toolbar: bool) -> None:
        action = dock_widget.toggleViewAction()
        action.setIcon(dock_widget.icon())
        holders = self._dock_action_holders() if toolbar else (self.viewMenu,)
        for holder in holders:
            holder.addAction(action)
        _apply_dock_view_tooltip(dock_widget, action)

    def _close_dock(self, dock_id: str) -> None:
        """Delete-on-close + closeDockWidget(): QtAds' own path for a docked, floating or auto-hidden dock."""
        _, dock_widget = self._docks.pop(dock_id, (None, None))
        if dock_widget is None or not shiboken6.isValid(dock_widget):
            return
        action = dock_widget.toggleViewAction()
        for holder in self._dock_action_holders():
            holder.removeAction(action)
        dock_widget.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)
        _queue_content_delete(dock_widget)
        dock_widget.closeDockWidget()

    def remove_native_plot_panel(self, panel: TimeSyncPanel):
        self.remove_panel(panel)

    def remove_panel(self, panel: Union[QWidget, str]):
        log.debug(f"Removing panel {panel}")
        if isinstance(panel, str):
            panel = self._panel_named(panel)
        dw = self._dock_of(panel) if panel is not None else None
        if dw:
            release_name(panel.objectName())
            _queue_content_delete(dw)
            dw.closeDockWidget()
            self._notify_panels_list_changed()

    def addWidgetIntoDock(self, allowed_area, widget, area=None, delete_on_close: bool = False,
                          size_hint_from_content: bool = True, custom_close_callback=None) -> Optional[
        QtAds.CDockAreaWidget]:
        if widget is not None:
            doc = QtAds.CDockWidget(widget.windowTitle())
            doc.setWidget(widget)
            if not widget.windowIcon().isNull():
                doc.setIcon(widget.windowIcon())
            if size_hint_from_content:
                doc.setMinimumSizeHintMode(QtAds.CDockWidget.MinimumSizeHintFromContent)
            dock_area = None
            area = area or self._find_biggest_area()
            if area:
                self.dock_manager.addDockWidgetTabToArea(doc, area)
            else:
                dock_area = self.dock_manager.addDockWidget(allowed_area, doc)
            if delete_on_close:
                doc.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)
                if custom_close_callback is not None:
                    doc.setFeature(QtAds.CDockWidget.CustomCloseHandling, True)
                    doc.closeRequested.connect(custom_close_callback)
                elif hasattr(widget, "delete_me"):
                    widget.delete_me.connect(doc.closeDockWidget)
            else:
                action = doc.toggleViewAction()
                self.viewMenu.addAction(action)
                _apply_dock_view_tooltip(doc, action)
            return dock_area
        return None

    def new_plot_panel(self, backend: str = "native", name: Optional[str] = None) -> Union[TimeSyncPanel, None]:
        if backend == "native":
            return self.new_native_plot_panel(name=name)
        return None

    def new_native_plot_panel(self, name: Optional[str] = None,
                              area: Optional[QtAds.CDockAreaWidget] = None) -> TimeSyncPanel:
        return self.open_panel(TIME_PANEL, name=name, area=area)

    def open_panel(self, kind_id: str, name: Optional[str] = None,
                   area: Optional[QtAds.CDockAreaWidget] = None, **config) -> QWidget:
        """Dock a new panel of a contributed kind. Raises NotRegistered for an unknown kind.
        simplify: open panels of a withdrawn kind stay open; close them on withdrawal when hot unload needs it."""
        kind = PANEL_KINDS.get(kind_id)
        if kind_id == TIME_PANEL:
            config.setdefault("time_range", self._default_time_range)
        name = auto_name(base=kind.label, name=name)
        try:
            widget = _create_panel(kind, name, config)
            _name_panel(widget, name, kind.icon)
            dock_panel(self, widget, kind_id, area)
        except Exception:
            release_name(name)
            raise
        return widget

    def _track_panel_dock(self, panel: TimeSyncPanel, dock_widget: QtAds.CDockWidget) -> None:
        """For panels docked outside new_native_plot_panel (e.g. VP debug panels):
        the X goes through remove_panel, and renames follow, like any other panel."""
        panel.setProperty(KIND_PROPERTY, TIME_PANEL)
        dock_widget.setFeature(QtAds.CDockWidget.CustomCloseHandling, True)
        dock_widget.closeRequested.connect(lambda: self.remove_panel(panel))
        _follow_panel_renames(panel, dock_widget)

    def _on_panel_dock_closed(self, dock_widget: QtAds.CDockWidget) -> None:
        # QtAds also emits `closed` when a dock is only hidden (toggleView(False));
        # a dock being deleted is unregistered from the manager before it emits.
        if self.dock_manager.findDockWidget(dock_widget.objectName()) is None:
            _destroy_content_before_its_window(dock_widget)

    def _schedule_dead_panel_drop(self, name: str) -> None:
        # Also fires while this window itself is being destroyed, when its own
        # C++ side is already gone: nothing left to clean up then.
        if shiboken6.isValid(self):
            QtCore.QTimer.singleShot(0, self, lambda: self._drop_dead_panel_dock(name))

    def _drop_dead_panel_dock(self, name: str) -> None:
        """A panel died without going through remove_panel (e.g. user code
        destroyed the widget directly). Drop its zombie dock entry so the dock
        layout and the panel enumeration stay consistent for sibling panels."""
        dw = self.dock_manager.findDockWidget(name)
        if dw is None or panel_of(dw) is not None:
            return
        log.warning(f"Panel {name!r} was destroyed without remove_panel; "
                    "cleaning up its dock entry")
        release_name(dw.windowTitle())
        container = dw.takeWidget()
        dw.closeDockWidget()
        if container is not None:
            container.deleteLater()
        self._notify_panels_list_changed()

    def _on_dock_area_created(self, area: QtAds.CDockAreaWidget) -> None:
        # dockAreaCreated fires from inside CDockAreaWidget's constructor,
        # before the triggering dock widget has been inserted into it —
        # defer the plot-panel check to the next event-loop turn so
        # dockWidgets() is populated by the time we look.
        QtCore.QTimer.singleShot(0, self, lambda: self._ensure_add_panel_button(area))

    def _ensure_add_panel_button(self, area: QtAds.CDockAreaWidget) -> None:
        if not shiboken6.isValid(area) or area.isAutoHide():
            return
        if area.property("sciqlop_add_panel_button") is not None:
            return
        button = QtWidgets.QToolButton(area)
        button.setAutoRaise(True)
        button.setIcon(theme_icon("add_graph"))
        button.setToolTip(rich_tooltip(
            "New plot panel",
            "Add a new plot panel as a tab in this area."))
        # Resolve the area from the button's live Qt parent chain at click
        # time, not by capturing `area` here: when the last panel in an
        # area is removed, QtAds reparents this button's title bar into a
        # different (or newly merged) area without emitting `destroyed` on
        # the old one and without updating its own
        # CDockAreaTitleBar.dockAreaWidget() backref -- both stay stale
        # indefinitely. The button survives and stays clickable, so a
        # captured `area` closure fires with an already-deleted C++
        # object. The real widget-tree parent, unlike QtAds's own backref,
        # is kept correct across the reparent.
        button.clicked.connect(lambda: self._add_panel_in_button_area(button))
        title_bar = area.titleBar()
        title_bar.insertWidget(title_bar.indexOf(title_bar.tabBar()) + 1, button)
        area.setProperty("sciqlop_add_panel_button", button)

    def _add_panel_in_button_area(self, button: QtWidgets.QToolButton) -> None:
        area = button.parentWidget().parentWidget()
        if shiboken6.isValid(area):
            self.new_native_plot_panel(area=area)

    def _panel_docks(self) -> List[Tuple[QtAds.CDockWidget, QWidget]]:
        return panel_docks(self)

    def _dock_of(self, panel: QWidget) -> Optional[QtAds.CDockWidget]:
        return next((dw for dw, p in self._panel_docks() if p is panel), None)

    def panels(self) -> List[QWidget]:
        """Every docked panel, of any kind."""
        return [p for _, p in self._panel_docks()]

    def _panel_named(self, name: str) -> Optional[QWidget]:
        # Not findDockWidget(name): docks stay keyed by their creation name after a rename.
        return next((p for p in self.panels() if p.objectName() == name), None)

    def _time_panels(self) -> List[TimeSyncPanel]:
        return [p for p in self.panels() if isinstance(p, TimeSyncPanel)]

    def plot_panels(self) -> List[str]:
        return [p.name for p in self._time_panels()]

    def plot_panel(self, name: str) -> Union[TimeSyncPanel, None]:
        return next((p for p in self._time_panels() if p.name == name), None)

    def _set_full_screen(self, full: bool) -> None:
        self.showFullScreen() if full else self.showNormal()

    def _on_workspace_already_loaded(self, workspace) -> None:
        """SCIQLOP_WORKSPACE_DIR makes the manager load its workspace while it is
        being constructed, before this window could connect to `workspace_loaded`."""
        self._show_workspace_name_in_title(workspace)
        self._maybe_run_onboarding_tour()

    def _show_workspace_name_in_title(self, workspace) -> None:
        self.setWindowTitle(f"SciQLop - {workspace.name}")

    def closeEvent(self, event: QCloseEvent):
        if not getattr(self, '_closing', False) and self._warn_if_jobs_running(event):
            return
        if not getattr(self, '_closing', False) and self._warn_if_catalogs_dirty(event):
            return
        if not getattr(self, '_closing', False):
            self._closing = True
            if self._schedule_async_close():
                event.ignore()
                return
            self._close_plugins_sync()
        workspaces_manager_instance().quit()
        super().closeEvent(event)

    def _warn_if_jobs_running(self, event: QCloseEvent) -> bool:
        from SciQLop.components.jobs.backend.jobs_backend import jobs_backend_instance
        try:
            jobs = jobs_backend_instance().list_jobs()
        except Exception:
            return False
        return _confirm_close_with_running_jobs(self, event, jobs)

    def _warn_if_catalogs_dirty(self, event: QCloseEvent) -> bool:
        return _confirm_close_with_dirty_catalogs(self, event, _dirty_catalog_names())

    @staticmethod
    def _usable_event_loop():
        """The qasync loop when it can actually run tasks, else None (e.g.
        pytest session teardown, where the loop never runs or asyncio.run()
        in a test has unset the current loop)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return None
        if loop.is_closed() or not loop.is_running():
            return None
        return loop

    def _schedule_async_close(self) -> bool:
        import asyncio
        loop = self._usable_event_loop()
        if loop is None:
            return False
        asyncio.ensure_future(self._async_close(), loop=loop)
        return True

    def _close_plugins_sync(self):
        """Fallback close when no event loop runs: plugins with coroutine
        close() get the coroutine closed unawaited — better a partial plugin
        cleanup than aborting the window close."""
        import inspect
        from SciQLop.components.plugins import loaded_plugins
        for plugin in loaded_plugins.__dict__.values():
            if hasattr(plugin, "close"):
                result = plugin.close()
                if inspect.isawaitable(result):
                    result.close()

    async def close_without_prompts(self):
        """Close plugins, then the window, skipping the running-jobs and
        unsaved-catalogs questions: in --batch nobody is there to answer them."""
        dirty = _dirty_catalog_names()
        if dirty:
            print(f"Warning: quitting with unsaved changes in: {', '.join(dirty)}. "
                  "Call save() on these catalogs in the script to keep them.", file=sys.stderr)
        self._closing = True
        await self._async_close()

    async def _async_close(self):
        import asyncio
        import inspect
        from SciQLop.components.plugins import loaded_plugins
        tasks = []
        for plugin in loaded_plugins.__dict__.values():
            if hasattr(plugin, "close"):
                result = plugin.close()
                if inspect.isawaitable(result):
                    tasks.append(asyncio.ensure_future(result))
        if tasks:
            await asyncio.wait(tasks, timeout=5.0)
        self.close()

    def push_variables_to_console(self, variables: dict):
        workspaces_manager_instance().push_variables(variable_dict=variables)

    def start(self):
        workspaces_manager_instance().start()

    def _maybe_run_onboarding_tour(self, *_args) -> None:
        from SciQLop.core.batch import in_batch_session
        if in_batch_session() or OnboardingSettings().completed_tours.get("getting_started", False):
            return
        self._tour_timer.start()

    def _start_getting_started_tour(self) -> None:
        self._start_tour("getting_started")

    def _refresh_tools_entries(self) -> None:
        for action in self._tools_entry_actions:
            self.toolsMenu.removeAction(action)
            action.deleteLater()
        before = self.toolsMenu.actions()
        add_menu_entries(self.toolsMenu, MAIN_TOOLS, {})
        self._tools_entry_actions = [a for a in self.toolsMenu.actions() if a not in before]

    def _open_tour_picker(self) -> None:
        from SciQLop.components.onboarding.ui.tour_picker import TourPicker
        picker = self._tour_picker
        if picker is not None and shiboken6.isValid(picker):
            picker.close()
        self._tour_picker = TourPicker(self)
        self._tour_picker.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self._tour_picker.show()

    def _start_tour(self, tour_id: str) -> None:
        controller = self._onboarding_controller
        if controller is not None and shiboken6.isValid(controller) and not controller.is_finished:
            controller.abort()
        self._onboarding_controller = run_tour(self, tour_id)

    def open_jupyterlab_widget(self):
        # Always re-request the widget, even when the dock exists: Lab's File menu
        # can shut its own server down or navigate to /logout, and jupyqt only
        # relaunches/reloads when asked for the widget again (SciQLop/jupyqt#10).
        jupyter_widget = workspaces_manager_instance().widget()
        existing = self.dock_manager.findDockWidget("SciQLop JupyterLab")
        if existing is not None:
            existing.toggleView(True)
            existing.raise_()
            return
        if jupyter_widget is not None:
            jupyter_widget.setWindowTitle("SciQLop JupyterLab")
            self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, jupyter_widget,
                                   size_hint_from_content=False)

    def _notify_panels_list_changed(self):
        self.panels_list_changed.emit(self.plot_panels())

    @property
    def name(self):
        return self.objectName()

import os
from datetime import datetime, timedelta
from typing import Optional, Union, List

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
from SciQLop.core.unique_names import auto_name, release_name
from SciQLop.components.workspaces import Workspace
from SciQLop.components.theming import register_icon, get_icon, get_current_style_icon, theme_icon, theme_adapted_icon, SciQLopStyle, qtads_stylesheet
from SciQLop.core.ui import Metrics
from SciQLop.core.ui.tooltips import rich_tooltip
from SciQLop.components.sciqlop_logging import getLogger
from SciQLopPlots import SciQLopMultiPlotPanel
from SciQLop.components.settings.ui import SettingsPanel
from SciQLop.components.catalogs.ui import CatalogBrowser
from SciQLop.components.onboarding.backend.settings import OnboardingSettings
from SciQLop.components.onboarding.ui.tour_controller import run_tour

__here__ = os.path.dirname(__file__)

register_icon("plot_panel", QtGui.QIcon("://icons/plot_panel_128.png"))

log = getLogger(__name__)


def _extract_panel(dock_widget):
    w = dock_widget.widget()
    if isinstance(w, PanelContainer):
        # the panel can die without going through remove_panel (e.g. user code
        # deleteLater'd it) — a dead Shiboken wrapper must not break the whole
        # panel enumeration
        return w.panel if shiboken6.isValid(w.panel) else None
    if isinstance(w, SciQLopMultiPlotPanel):
        return w
    return None


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


class SciQLopMainWindow(QtWidgets.QMainWindow):
    AUTO_HIDE_TAB_ICON = 2.2  # em — side bar tab icon, set here because
    # qproperty-iconSize does not survive a theme change (see _apply_dock_theme)
    workspace: Workspace = None
    panels_list_changed = QtCore.Signal(list)
    panel_added = QtCore.Signal(TimeSyncPanel)

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

        self.toolsMenu = QMenu("Tools")
        self.toolsMenu.setToolTipsVisible(True)
        self._menubar.addMenu(self.toolsMenu)
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
            "Take a Tour…", self._open_tour_picker)
        take_a_tour.setToolTip(rich_tooltip(
            "Take a Tour",
            "Pick a guided walkthrough of a SciQLop feature."))

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
        wm.push_variables({"main_window": wm.wrap_qt(self)})
        wm.workspace_loaded.connect(lambda w: self.setWindowTitle(f"SciQLop - {w.name}"))
        from SciQLop.components.onboarding.backend.registry import register_builtin_tours
        register_builtin_tours()
        self._onboarding_controller = None
        self._tour_picker = None
        wm.workspace_loaded.connect(self._maybe_run_onboarding_tour)
        sciqlop_app().add_quickstart_shortcut("JupyterLab", "Open JupyterLab",
                                              Icons.get_icon("Jupyter"),
                                              self.open_jupyterlab_widget)
        open_browser = self.toolsMenu.addAction(
            "Open JupyterLab in browser", wm.open_in_browser)
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
        self.setWindowTitle("SciQLop")
        self.setWindowIcon(QtGui.QIcon("://icons/SciQLop.png"))
        self.toolBar = QtWidgets.QToolBar(self)
        self.toolBar.setWindowTitle("Toolbar")
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, self.toolBar)
        self.toolBar.setVisible(False)
        self.viewMenu.addAction(self.toolBar.toggleViewAction())

        self.addTSPanel = QtGui.QAction(self)
        self.addTSPanel.setIcon(theme_icon("add_graph"))
        self.addTSPanel.setText("Add new plot panel")
        self.addTSPanel.setToolTip(rich_tooltip(
            "New plot panel",
            "Create an empty panel to drop products onto."))
        self.addTSPanel.triggered.connect(lambda: self.new_plot_panel())
        self.toolBar.addAction(self.addTSPanel)
        sciqlop_app().add_quickstart_shortcut(name="Plot panel", description="Add a new plot panel",
                                              icon=theme_icon("add_graph"), callback=self.new_plot_panel)
        sciqlop_app().add_quickstart_shortcut(
            name="Take a Tour", description="Pick a guided walkthrough of a SciQLop feature",
            icon=theme_icon("assistant"), callback=self._open_tour_picker)

    def _setup_status_bar(self):
        self._statusbar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self._statusbar)
        self._statusbar.setFixedHeight(Metrics.ex(1.5))

        self._mem_usage = QtWidgets.QProgressBar()
        self._sys_mem = psutil.virtual_memory().total // 1024 ** 2
        self._mem_usage.setMaximum(self._sys_mem)
        self._mem_usage.setFormat(f"System memory usage: %v / {self._sys_mem:.2f} MB")

        self._cpu_usage = QtWidgets.QProgressBar()
        self._cpu_usage.setFormat("CPU usage: %v%")

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

        shortcut = QtGui.QShortcut(QtGui.QKeySequence(palette_settings.keybinding), self)
        shortcut.activated.connect(self._command_palette.toggle)

    def _show_logs(self):
        dw = self.dock_manager.findDockWidget(self.logs.windowTitle())
        if dw is None:
            self.addWidgetIntoDock(QtAds.DockWidgetArea.BottomDockWidgetArea, self.logs)
        else:
            dw.toggleView(True)
            dw.raise_()

    def _show_appstore(self):
        if self._appstore is None:
            from SciQLop.components.appstore import AppStorePage
            self._appstore = AppStorePage()
            self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, self._appstore)
        else:
            dw = self.dock_manager.findDockWidget(self._appstore.windowTitle())
            if dw:
                dw.toggleView(True)
                dw.raise_()

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

    def add_side_pan(self, widget: QWidget, location=QtAds.PySide6QtAds.ads.SideBarLocation.SideBarLeft, icon=None):
        if widget is not None:
            doc = QtAds.CDockWidget(widget.windowTitle())
            doc.setWidget(widget, QtAds.CDockWidget.ForceNoScrollArea)
            doc.setMinimumSizeHintMode(QtAds.CDockWidget.MinimumSizeHintFromContent)
            if icon is not None:
                if os.path.exists(icon):
                    doc.setIcon(QIcon(icon))
                else:
                    doc.setIcon(get_icon(icon))
            elif widget.windowIcon() is not None:
                doc.setIcon(widget.windowIcon())
            container = self.dock_manager.addAutoHideDockWidget(location, doc)
            container.autoHideTab().setIconSize(Metrics.icon_size(self.AUTO_HIDE_TAB_ICON))
            if location == QtAds.PySide6QtAds.ads.SideBarLocation.SideBarBottom or location == QtAds.PySide6QtAds.ads.SideBarLocation.SideBarTop:
                container.setSize(widget.sizeHint().height())
            else:
                container.setSize(widget.sizeHint().width())
            self.viewMenu.addAction(doc.toggleViewAction())

    def remove_native_plot_panel(self, panel: TimeSyncPanel):
        dw = self.dock_manager.findDockWidget(panel.name)
        if dw:
            container = dw.takeWidget()
            dw.closeDockWidget()
            container.deleteLater()

    def remove_panel(self, panel: Union[TimeSyncPanel, str]):
        log.debug(f"Removing panel {panel}")
        if isinstance(panel, str):
            panel = self.plot_panel(panel)
        if panel:
            dw = self.dock_manager.findDockWidget(panel.name)
            if dw:
                release_name(panel.name)
                container = dw.takeWidget()
                dw.closeDockWidget()
                container.deleteLater()
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
                if custom_close_callback is not None:
                    doc.setFeature(QtAds.CDockWidget.CustomCloseHandling, True)
                    doc.closeRequested.connect(custom_close_callback)
                else:
                    doc.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)
                    if hasattr(widget, "delete_me"):
                        widget.delete_me.connect(doc.closeDockWidget)
            else:
                self.viewMenu.addAction(doc.toggleViewAction())
            return dock_area
        return None

    def new_plot_panel(self, backend: str = "native", name: Optional[str] = None) -> Union[TimeSyncPanel, None]:
        if backend == "native":
            return self.new_native_plot_panel(name=name)
        return None

    def new_native_plot_panel(self, name: Optional[str] = None,
                              area: Optional[QtAds.CDockAreaWidget] = None) -> TimeSyncPanel:
        panel = TimeSyncPanel(parent=None, name=auto_name(base="Panel", name=name),
                              time_range=self._default_time_range)
        container = PanelContainer(panel)
        self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, container,
                               area=area, delete_on_close=True)
        dock_widget = self.dock_manager.findDockWidget(panel.name)
        if dock_widget is not None:
            # addWidgetIntoDock may have tabbed this panel into an existing
            # area (e.g. the welcome page's) via _find_biggest_area() rather
            # than creating a fresh one — dockAreaCreated only fires for the
            # latter, so that path alone misses this, very common, case.
            self._ensure_add_panel_button(dock_widget.dockAreaWidget())
        panel.delete_me.connect(lambda: self.remove_panel(panel))
        self.panel_added.emit(panel)
        self._notify_panels_list_changed()
        panel.destroyed.connect(self._notify_panels_list_changed)
        panel_name = panel.name
        panel.destroyed.connect(
            lambda *_: QtCore.QTimer.singleShot(
                0, lambda: self._drop_dead_panel_dock(panel_name)))
        return panel

    def _drop_dead_panel_dock(self, name: str) -> None:
        """A panel died without going through remove_panel (e.g. user code
        destroyed the widget directly). Drop its zombie dock entry so the dock
        layout and the panel enumeration stay consistent for sibling panels."""
        dw = self.dock_manager.findDockWidget(name)
        if dw is None or _extract_panel(dw) is not None:
            return
        log.warning(f"Panel {name!r} was destroyed without remove_panel; "
                    "cleaning up its dock entry")
        release_name(name)
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
        QtCore.QTimer.singleShot(0, lambda: self._ensure_add_panel_button(area))

    def _ensure_add_panel_button(self, area: QtAds.CDockAreaWidget) -> None:
        if not shiboken6.isValid(area):
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

    def plot_panels(self) -> List[str]:
        panels = [_extract_panel(dw) for dw in self.dock_manager.dockWidgets()]
        return [p.name for p in panels if p is not None]

    def plot_panel(self, name: str) -> Union[TimeSyncPanel, None]:
        dw: QtAds.CDockWidget = self.dock_manager.findDockWidget(name)
        if dw:
            return _extract_panel(dw)
        return None

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

    def closeEvent(self, event: QCloseEvent):
        if not getattr(self, '_closing', False) and self._warn_if_jobs_running(event):
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
        if OnboardingSettings().completed_tours.get("getting_started", False):
            return
        QtCore.QTimer.singleShot(500, lambda: self._start_tour("getting_started"))

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
            return
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

import os
from datetime import datetime, timedelta
from typing import Optional, Union, List

import humanize
import psutil

import PySide6QtAds as QtAds
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QWidget, QMenu

from SciQLop.components.workspaces import workspaces_manager_instance
from SciQLop.components.sciqlop_logging.logs_widget import LogsWidget
from SciQLopPlots import PropertiesPanel, ProductsView, Icons
from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
from SciQLop.components.plotting.ui.panel_container import PanelContainer
from SciQLop.components.welcome import WelcomePage
from SciQLop.core import TimeRange
from SciQLop.core.sciqlop_application import sciqlop_app
from SciQLop.core.unique_names import auto_name
from SciQLop.components.workspaces import Workspace
from SciQLop.components.theming import register_icon, get_icon, get_current_style_icon, SciQLopStyle
from SciQLop.core.ui import Metrics
from SciQLop.components.sciqlop_logging import getLogger
from SciQLopPlots import SciQLopMultiPlotPanel
from SciQLop.components.settings.ui import SettingsPanel
from SciQLop.components.catalogs.ui import CatalogBrowser

__here__ = os.path.dirname(__file__)

register_icon("plot_panel", QtGui.QIcon("://icons/plot_panel_128.png"))
register_icon("tree", QtGui.QIcon(f"{__here__}/../../resources/icons/tree.png"))
register_icon("settings", QtGui.QIcon(f"{__here__}/../../resources/icons/settings.png"))
register_icon("view_list", QtGui.QIcon(f"{__here__}/../../resources/icons/view_list.png"))
register_icon("home", QtGui.QIcon(f"{__here__}/../../resources/icons/home.png"))

register_icon("plot_properties", QtGui.QIcon(f"{__here__}/../../resources/icons/plot_properties.svg"))

log = getLogger(__name__)


def _extract_panel(dock_widget):
    w = dock_widget.widget()
    if isinstance(w, PanelContainer):
        return w.panel
    if isinstance(w, SciQLopMultiPlotPanel):
        return w
    return None


def _surface(size: QtCore.QSize):
    return size.width() * size.height()


class SciQLopMainWindow(QtWidgets.QMainWindow):
    workspace: Workspace = None
    panels_list_changed = QtCore.Signal(list)
    panel_added = QtCore.Signal(TimeSyncPanel)

    def __init__(self):

        QtWidgets.QMainWindow.__init__(self)
        self.setObjectName("SciQLopMainWindow")
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
        self.toolsMenu.addAction("Plugin Store", self._show_appstore)
        self.welcome.backend.appstore_requested.connect(self._show_appstore)

        self._center_and_maximise_on_screen()

    def _setup_dock_manager(self):
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FocusHighlighting, True)
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FloatingContainerHasWidgetIcon, True)
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
        self.dock_manager.setStyleSheet("")

    def _setup_menus(self):
        self._menubar = QtWidgets.QMenuBar(self)
        self.setMenuBar(self._menubar)
        self._menubar.setGeometry(QtCore.QRect(0, 0, 615, 23))
        self._menubar.setDefaultUp(True)

        self.viewMenu = QMenu("View")
        self._menubar.addMenu(self.viewMenu)
        self.viewMenu.addAction("Reload theme",
                                lambda: sciqlop_app().apply_theme(SciQLopStyle().color_palette))

        self.toolsMenu = QMenu("Tools")
        self._menubar.addMenu(self.toolsMenu)
        self.toolsMenu.addAction("Open JupyterLab", self.open_jupyterlab_widget)

    def _setup_side_panels(self):
        self.productTree = ProductsView(self)
        self.productTree.setWindowIcon(get_current_style_icon("tree"))
        self.add_side_pan(self.productTree)

        from SciQLop.components.products.product_context_menu import setup_product_context_menu
        setup_product_context_menu(self.productTree, self)

        self.catalogs_browser = CatalogBrowser(self)
        self.catalogs_browser.setWindowIcon(get_current_style_icon("catalogue"))
        self.add_side_pan(self.catalogs_browser)
        self.panel_added.connect(self.catalogs_browser.connect_to_panel)

        wm = workspaces_manager_instance()
        wm.push_variables({"main_window": wm.wrap_qt(self)})
        wm.workspace_loaded.connect(lambda w: self.setWindowTitle(f"SciQLop - {w.name}"))
        sciqlop_app().add_quickstart_shortcut("JupyterLab", "Open JupyterLab",
                                              Icons.get_icon("Jupyter"),
                                              self.open_jupyterlab_widget)
        self.toolsMenu.addAction("Open JupyterLab in browser", wm.open_in_browser)

        self.logs = LogsWidget(self)
        self.logs.setWindowIcon(get_current_style_icon("view_list"))
        self.add_side_pan(self.logs, QtAds.PySide6QtAds.ads.SideBarLocation.SideBarBottom)

        self.settings_panel = SettingsPanel(self)
        self.settings_panel.setWindowIcon(get_icon("settings"))
        self.settings_panel.setWindowTitle("Settings")
        self.add_side_pan(self.settings_panel)

        self.properties_panel = PropertiesPanel(self)
        self.properties_panel.setWindowIcon(get_icon("plot_properties"))
        self.add_side_pan(self.properties_panel)

    def _setup_toolbar(self):
        self.setWindowTitle("SciQLop")
        self.setWindowIcon(QtGui.QIcon("://icons/SciQLop.png"))
        self.toolBar = QtWidgets.QToolBar(self)
        self.toolBar.setWindowTitle("Toolbar")
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, self.toolBar)

        self.addTSPanel = QtGui.QAction(self)
        self.addTSPanel.setIcon(get_current_style_icon("add_graph"))
        self.addTSPanel.setText("Add new plot panel")
        self.addTSPanel.triggered.connect(lambda: self.new_plot_panel())
        self.toolBar.addAction(self.addTSPanel)
        sciqlop_app().add_quickstart_shortcut(name="Plot panel", description="Add a new plot panel",
                                              icon=get_icon("plot_panel"), callback=self.new_plot_panel)

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
        self._stats_toggle.setToolTip("Show system stats")
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
        self._stats_toggle.setToolTip("Hide system stats" if visible else "Show system stats")

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

    def new_native_plot_panel(self, name: Optional[str] = None) -> TimeSyncPanel:
        panel = TimeSyncPanel(parent=None, name=auto_name(base="Panel", name=name),
                              time_range=self._default_time_range)
        container = PanelContainer(panel)
        self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, container, delete_on_close=True)
        self.panel_added.emit(panel)
        self._notify_panels_list_changed()
        panel.destroyed.connect(self._notify_panels_list_changed)
        return panel

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
        if not getattr(self, '_closing', False):
            event.ignore()
            self._closing = True
            import asyncio
            asyncio.ensure_future(self._async_close())
            return
        workspaces_manager_instance().quit()
        super().closeEvent(event)

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

    def open_jupyterlab_widget(self):
        existing = self.dock_manager.findDockWidget("SciQLop JupyterLab")
        if existing is not None:
            existing.toggleView(True)
            existing.raise_()
            return
        jupyter_widget = workspaces_manager_instance().widget()
        if jupyter_widget is not None:
            jupyter_widget.setWindowTitle("SciQLop JupyterLab")
            self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, jupyter_widget,
                                   size_hint_from_content=False)

    def _notify_panels_list_changed(self):
        self.panels_list_changed.emit(self.plot_panels())

    @property
    def name(self):
        return self.objectName()

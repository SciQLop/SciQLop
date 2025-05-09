import os
from datetime import datetime, timedelta
from typing import Optional, Union, List

import humanize
import psutil

import PySide6QtAds as QtAds
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QWidget, QMenu

from .workspaces import WorkspaceManagerUI
from .JupyterLabView import JupyterLabView
from .logs_widget import LogsWidget
from .datetime_range import DateTimeRangeWidgetAction
from SciQLopPlots import PropertiesPanel, ProductsView
from .plots.time_sync_panel import TimeSyncPanel
from .welcome import WelcomePage
from ..backend import TimeRange
from ..backend.sciqlop_application import sciqlop_app
from ..backend.unique_names import auto_name
from ..backend.workspace import Workspace
from ..backend.icons import register_icon, Icons
from ..backend.sciqlop_logging import getLogger
from SciQLopPlots import SciQLopMultiPlotPanel, Icons

__here__ = os.path.dirname(__file__)

register_icon("plot_panel", QtGui.QIcon("://icons/plot_panel_128.png"))
register_icon("tree", QtGui.QIcon(f"{__here__}/../resources/icons/tree.svg"))
register_icon("plot_properties", QtGui.QIcon(f"{__here__}/../resources/icons/plot_properties.svg"))

log = getLogger(__name__)


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
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FocusHighlighting, True)
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FloatingContainerHasWidgetIcon, True)


        QtAds.CDockManager.setAutoHideConfigFlags(
            QtAds.CDockManager.AutoHideFeatureEnabled |
            QtAds.CDockManager.AutoHideCloseButtonCollapsesDock |
            QtAds.CDockManager.AutoHideHasMinimizeButton |
            QtAds.CDockManager.AutoHideShowOnMouseOver |
            QtAds.CDockManager.AutoHideOpenOnDragHover
        )

        if "WAYLAND_DISPLAY" in os.environ:
            QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FloatingContainerForceQWidgetTitleBar, True)
        self.dock_manager = QtAds.CDockManager(self)
        self.dock_manager.setStyleSheet("")
        self._menubar = QtWidgets.QMenuBar(self)
        self.setMenuBar(self._menubar)
        self._menubar.setGeometry(QtCore.QRect(0, 0, 615, 23))
        self._menubar.setDefaultUp(True)
        self.viewMenu = QMenu("View")
        self._menubar.addMenu(self.viewMenu)
        self.viewMenu.addAction("Reload stylesheets", sciqlop_app().load_stylesheet)

        default_time_range = TimeRange((datetime.utcnow() - timedelta(days=361)).timestamp(),
                                       (datetime.utcnow() - timedelta(days=360)).timestamp())

        self.toolsMenu = QMenu("Tools")
        self._menubar.addMenu(self.toolsMenu)
        self.welcome = WelcomePage()

        self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, self.welcome)

        self.productTree = ProductsView(self)
        self.productTree.setWindowIcon(Icons.get_icon("tree"))
        self.add_side_pan(self.productTree)

        self.workspace_manager = WorkspaceManagerUI(self)
        self.workspace_manager.pushVariables({"main_window": self})
        self.workspace_manager.workspace_loaded.connect(lambda ws: self.setWindowTitle(f"SciQLop - {ws}"))
        self.workspace_manager.jupyterlab_started.connect(
            lambda url: self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, JupyterLabView(None, url),
                                               size_hint_from_content=False))
        self.add_side_pan(self.workspace_manager, QtAds.PySide6QtAds.ads.SideBarLocation.SideBarBottom)
        self.toolsMenu.addAction("Start jupyter console", self.workspace_manager.new_qt_console)

        self.logs = LogsWidget(self)
        self.add_side_pan(self.logs, QtAds.PySide6QtAds.ads.SideBarLocation.SideBarBottom)

        self.setWindowTitle("SciQLop")
        self.toolBar = QtWidgets.QToolBar(self)
        self.toolBar.setWindowTitle("Toolbar")
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, self.toolBar)
        self._dt_range_action = DateTimeRangeWidgetAction(self, default_time_range=default_time_range)
        self.toolBar.addAction(self._dt_range_action)
        self.addTSPanel = QtGui.QAction(self)
        self.addTSPanel.setIcon(QtGui.QIcon("://icons/theme/add_graph.png"))
        self.addTSPanel.setText("Add new plot panel")
        self.addTSPanel.triggered.connect(lambda: self.new_plot_panel())
        self.toolBar.addAction(self.addTSPanel)
        sciqlop_app().add_quickstart_shortcut(name="Plot panel", description="Add a new plot panel",
                                              icon=Icons.get_icon("plot_panel"), callback=self.new_plot_panel)
        self.setWindowIcon(QtGui.QIcon("://icons/SciQLop.png"))

        self._statusbar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self._statusbar)
        self._statusbar.setMaximumHeight(28)

        self.properties_panel = PropertiesPanel(self)
        self.properties_panel.setWindowIcon(Icons.get_icon("plot_properties"))
        self.add_side_pan(self.properties_panel)

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

        self._statusbar.addPermanentWidget(self._network_usage_recv_speed)
        self._statusbar.addPermanentWidget(self._network_usage_send_speed)
        self._statusbar.addPermanentWidget(self._cpu_usage)
        self._statusbar.addPermanentWidget(self._mem_usage)

        self._refresh_mem_timer = QtCore.QTimer(self)
        self._refresh_mem_timer.timeout.connect(self._update_usage)
        self._refresh_mem_timer.start(1000)

        self._center_and_maximise_on_screen()

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
    def defaul_range(self):
        return self._dt_range_action.range

    def add_side_pan(self, widget: QWidget, location=QtAds.PySide6QtAds.ads.SideBarLocation.SideBarLeft, icon=None):
        if widget is not None:
            doc = QtAds.CDockWidget(widget.windowTitle())
            doc.setWidget(widget, QtAds.CDockWidget.ForceNoScrollArea)
            doc.setMinimumSizeHintMode(QtAds.CDockWidget.MinimumSizeHintFromContent)
            if icon is not None:
                if os.path.exists(icon):
                    doc.setIcon(QIcon(icon))
                else:
                    doc.setIcon(Icons.get_icon(icon))
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
            dw.takeWidget()
            dw.closeDockWidget()
            panel.deleteLater()

    def remove_panel(self, panel: Union[TimeSyncPanel, str]):
        log.debug(f"Removing panel {panel}")
        if isinstance(panel, str):
            panel = self.plot_panel(panel)
        if panel:
            dw = self.dock_manager.findDockWidget(panel.name)
            if dw:
                dw.takeWidget()
                dw.closeDockWidget()
                panel.deleteLater()
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
        # elif backend == "mpl":
        #    return self.new_mpl_plot_panel()
        return None

    def new_native_plot_panel(self, name: Optional[str] = None) -> TimeSyncPanel:
        panel = TimeSyncPanel(parent=None, name=auto_name(base="Panel", name=name),
                              time_range=self._dt_range_action.range)
        self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, panel, delete_on_close=True)
        self.panel_added.emit(panel)
        self._notify_panels_list_changed()
        panel.destroyed.connect(self._notify_panels_list_changed)
        return panel

    # def new_mpl_plot_panel(self) -> MPLPanel:
    #    panel = MPLPanel(parent=None, name=make_simple_incr_name(base="Panel"),
    #                     time_range=self._dt_range_action.range)
    #    self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, panel, delete_on_close=True)
    #    panel.destroyed.connect(self._notify_panels_list_changed)
    #    self._notify_panels_list_changed()
    #    # self._inspector_model.new_top_level_object(panel)
    #    return panel

    def plot_panels(self) -> List[str]:
        return list(
            map(lambda dw: dw.widget().name,
                filter(lambda dw: isinstance(dw.widget(), SciQLopMultiPlotPanel), self.dock_manager.dockWidgets())))

    def plot_panel(self, name: str) -> Union[TimeSyncPanel, None]:
        widget: QtAds.CDockWidget = self.dock_manager.findDockWidget(name)
        if widget:
            return widget.widget()
        return None

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

    def closeEvent(self, event: QCloseEvent):
        self.workspace_manager.quit()
        super().closeEvent(event)
        from SciQLop.plugins import loaded_plugins
        for plugin in loaded_plugins.__dict__.values():
            if hasattr(plugin, "close"):
                plugin.close()

    def push_variables_to_console(self, variables: dict):
        self.workspace_manager.pushVariables(variable_dict=variables)

    def start(self):
        self.workspace_manager.start()

    def _notify_panels_list_changed(self):
        self.panels_list_changed.emit(self.plot_panels())

    @property
    def name(self):
        return self.objectName()

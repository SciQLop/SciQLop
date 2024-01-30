import os
from datetime import datetime, timedelta
from typing import Optional, Union, List, Any

import PySide6QtAds as QtAds
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtGui import QCloseEvent, Qt
from PySide6.QtWidgets import QWidget, QSizePolicy, QMenu

from .IPythonManager import IPythonKernelManager
from .workspaces import WorkspaceManagerUI
from .JupyterLabView import JupyterLabView
from .logs_widget import LogsWidget
from .datetime_range import DateTimeRangeWidgetAction
from .inspector import InspectorWidget
from .plots.abstract_plot_panel import PlotPanel
from .plots.mpl_panel import MPLPanel
from .plots.time_sync_panel import TimeSyncPanel
from .products_tree import ProductTree as PyProductTree
from .welcome import WelcomePage
from ..backend import TimeRange
from ..backend.sciqlop_application import sciqlop_app, SciQLopApp
from ..backend.unique_names import make_simple_incr_name
from ..inspector.model import Model as InspectorModel
from ..inspector.inspector import register_inspector, Inspector
from ..inspector.node import Node, RootNode
from ..backend.workspace import Workspace


class SciQLopMainWindow(QtWidgets.QMainWindow):
    panels_list_changed = QtCore.Signal(list)
    workspace: Workspace = None
    app: SciQLopApp = None

    def __init__(self):

        QtWidgets.QMainWindow.__init__(self)
        self.setObjectName("SciQLopMainWindow")
        self.app = sciqlop_app()
        self._setup_ui(self.app)
        self.app.panels_list_changed.connect(self.panels_list_changed)

    def _setup_ui(self, app):
        QtAds.CDockManager.setAutoHideConfigFlag(QtAds.CDockManager.DefaultAutoHideConfig)
        QtAds.CDockManager.setAutoHideConfigFlag(QtAds.CDockManager.AutoHideShowOnMouseOver, True)

        if "WAYLAND_DISPLAY" in os.environ:
            QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FloatingContainerForceQWidgetTitleBar, True)
        self.dock_manager = QtAds.CDockManager(self)
        self._menubar = QtWidgets.QMenuBar(self)
        self.setMenuBar(self._menubar)
        self._menubar.setGeometry(QtCore.QRect(0, 0, 615, 23))
        self._menubar.setDefaultUp(True)
        self.viewMenu = QMenu("View")
        self._menubar.addMenu(self.viewMenu)

        default_time_range = TimeRange((datetime.utcnow() - timedelta(days=361)).timestamp(),
                                       (datetime.utcnow() - timedelta(days=360)).timestamp())

        self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, WelcomePage())

        self.productTree = PyProductTree(self)
        self.add_side_pan(self.productTree)

        self.workspace_manager = WorkspaceManagerUI(self)
        self.workspace_manager.pushVariables({"main_window": self})
        self.workspace_manager.jupyterlab_started.connect(
            lambda url: self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, JupyterLabView(None, url)))
        self.add_side_pan(self.workspace_manager, QtAds.PySide6QtAds.ads.SideBarLocation.SideBarBottom)

        # self.ipython_kernel_manager = IPythonKernelManager(parent=self, app=app, available_vars={"main_window": self})
        # self.ipython_kernel_manager.jupyterlab_started.connect(
        #    lambda url: self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, JupyterLabView(None, url)))
        # self.add_side_pan(self.ipython_kernel_manager, QtAds.PySide6QtAds.ads.SideBarLocation.SideBarBottom)
        self.logs = LogsWidget(self)
        self.add_side_pan(self.logs, QtAds.PySide6QtAds.ads.SideBarLocation.SideBarBottom)

        self.setWindowTitle("SciQLop")
        self.toolBar = QtWidgets.QToolBar(self)
        self.toolBar.setWindowTitle("Toolbar")
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, self.toolBar)
        self._dt_range_action = DateTimeRangeWidgetAction(self, default_time_range=default_time_range)
        self.toolBar.addAction(self._dt_range_action)
        self.addTSPanel = QtGui.QAction(self)
        self.addTSPanel.setIcon(QtGui.QIcon("://icons/add.png"))
        self.addTSPanel.triggered.connect(lambda: self.new_plot_panel())
        self.toolBar.addAction(self.addTSPanel)
        self.setWindowIcon(QtGui.QIcon("://icons/SciQLop.png"))
        self.resize(1024, 768)

        self._statusbar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self._statusbar)

        self._inspector_model = InspectorModel(parent=self, root_object=self)
        self.inspector_ui = InspectorWidget(model=self._inspector_model, parent=self)
        self.add_side_pan(self.inspector_ui)
        self.panels_list_changed.connect(self._inspector_model.root_node.changed)

    def add_side_pan(self, widget: QWidget, location=QtAds.PySide6QtAds.ads.SideBarLocation.SideBarLeft):
        if widget is not None:
            widget.setMinimumWidth(100)
            widget.setMinimumHeight(100)
            widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
            doc = QtAds.CDockWidget(widget.windowTitle())
            doc.setWidget(widget)
            doc.setMinimumSizeHintMode(QtAds.CDockWidget.MinimumSizeHintFromContent)
            doc.setMinimumWidth(300)
            doc.setMinimumHeight(300)
            self.dock_manager.addAutoHideDockWidget(location, doc)
            self.viewMenu.addAction(doc.toggleViewAction())

    def addWidgetIntoDock(self, allowed_area, widget, area=None, delete_on_close: bool = False) -> Optional[
        QtAds.CDockAreaWidget]:
        if widget is not None:
            doc = QtAds.CDockWidget(widget.windowTitle())
            doc.setWidget(widget)
            dock_aera = self.dock_manager.addDockWidget(allowed_area, doc)
            if area:
                self.dock_manager.addDockWidgetTabToArea(doc, area)
            if delete_on_close:
                doc.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)
                if hasattr(widget, "delete_me"):
                    widget.delete_me.connect(doc.closeDockWidget)
            else:
                self.viewMenu.addAction(doc.toggleViewAction())
            return dock_aera
        return None

    def new_plot_panel(self, backend: str = "native") -> Union[TimeSyncPanel, MPLPanel, None]:
        if backend == "native":
            return self.new_native_plot_panel()
        elif backend == "mpl":
            return self.new_mpl_plot_panel()
        return None

    def new_native_plot_panel(self) -> TimeSyncPanel:
        panel = TimeSyncPanel(parent=None, name=make_simple_incr_name(base="Panel"),
                              time_range=self._dt_range_action.range)
        self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, panel, delete_on_close=True)
        panel.destroyed.connect(self._notify_panels_list_changed)
        self._notify_panels_list_changed()
        # self._inspector_model.new_top_level_object(panel)
        return panel

    def new_mpl_plot_panel(self) -> MPLPanel:
        panel = MPLPanel(parent=None, name=make_simple_incr_name(base="Panel"),
                         time_range=self._dt_range_action.range)
        self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, panel, delete_on_close=True)
        panel.destroyed.connect(self._notify_panels_list_changed)
        self._notify_panels_list_changed()
        # self._inspector_model.new_top_level_object(panel)
        return panel

    def plot_panels(self) -> List[str]:
        return list(
            map(lambda dw: dw.widget().name,
                filter(lambda dw: isinstance(dw.widget(), PlotPanel), self.dock_manager.dockWidgets())))

    def plot_panel(self, name: str) -> Union[TimeSyncPanel, MPLPanel, None]:
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

    def push_variables_to_console(self, variables: dict):
        self.workspace_manager.pushVariables(variable_dict=variables)

    def start(self):
        self.workspace_manager.start()

    def _notify_panels_list_changed(self):
        self.panels_list_changed.emit(self.plot_panels())

    @property
    def name(self):
        return self.objectName()


@register_inspector(SciQLopMainWindow)
class SciQLopMainWindowInspector(Inspector):

    @staticmethod
    def build_node(obj: Any, parent: Optional[Node] = None, children: Optional[List[Node]] = None) -> Optional[Node]:
        return RootNode(top_obj=obj)

    @staticmethod
    def list_children(obj: Any) -> List[Any]:
        return list(map(obj.plot_panel, obj.plot_panels()))

    @staticmethod
    def child(obj: Any, name: str) -> Optional[Any]:
        assert (isinstance(obj, SciQLopMainWindow))
        return obj.plot_panel(name)

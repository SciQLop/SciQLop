from datetime import datetime, timedelta

import PySide6QtAds as QtAds
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QWidget, QSizePolicy, QMenu

from .central_widget import CentralWidget
from .console import Console
from .datetime_range import DateTimeRangeWidgetAction
from .pipelines import PipelineTree
from .plots.time_sync_panel import TimeSyncPanel
from .products_tree import ProductTree as PyProductTree
from ..backend import TimeRange
from SciQLop.backend.models import pipelines


class SciQLopMainWindow(QtWidgets.QMainWindow):
    def __init__(self):

        QtWidgets.QMainWindow.__init__(self)
        self._setup_ui()

    def _setup_ui(self):
        QtAds.CDockManager.setAutoHideConfigFlag(QtAds.CDockManager.DefaultAutoHideConfig)
        self.dock_manager = QtAds.CDockManager(self)
        self._menubar = QtWidgets.QMenuBar(self)
        self.setMenuBar(self._menubar)
        self._menubar.setGeometry(QtCore.QRect(0, 0, 615, 23))
        self._menubar.setDefaultUp(True)
        self.viewMenu = QMenu("View")
        self._menubar.addMenu(self.viewMenu)

        default_time_range = TimeRange((datetime.utcnow() - timedelta(days=361)).timestamp(),
                                       (datetime.utcnow() - timedelta(days=360)).timestamp())
        self.central_widget = CentralWidget(self, time_range=default_time_range)
        self.central_widget.dock_widget_added.connect(lambda dw: self.viewMenu.addAction(dw.toggleViewAction()))
        central_dock_widget = QtAds.CDockWidget("Plot Area")
        central_dock_widget.setWidget(self.central_widget)
        central_dock_area = self.dock_manager.setCentralWidget(central_dock_widget)
        central_dock_area.setAllowedAreas(QtAds.DockWidgetArea.OuterDockAreas)

        self.productTree = PyProductTree(self)
        self.add_side_pan(self.productTree)
        self.pipelinesTree = PipelineTree(self)
        self.add_side_pan(self.pipelinesTree)
        self.console = Console(parent=self, available_vars={"main_window": self},
                               custom_banner="SciQLop IPython Console ")
        self.addWidgetIntoDock(QtAds.BottomDockWidgetArea, self.console)
        self.setWindowTitle("SciQLop")
        self.toolBar = QtWidgets.QToolBar(self)
        self.toolBar.setWindowTitle("Toolbar")
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, self.toolBar)
        self._dt_range_action = DateTimeRangeWidgetAction(self, default_time_range=default_time_range)
        self.toolBar.addAction(self._dt_range_action)
        self._dt_range_action.range_changed.connect(self.central_widget.set_default_time_range)
        self.addTSPanel = QtGui.QAction(self)
        self.addTSPanel.setIcon(QtGui.QIcon("://icons/add.png"))
        self.addTSPanel.triggered.connect(lambda: self.new_plot_panel())
        self.toolBar.addAction(self.addTSPanel)
        self.setWindowIcon(QtGui.QIcon("://icons/SciQLop.png"))
        self.resize(1024, 768)

        self._statusbar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self._statusbar)

    def add_side_pan(self, widget: QWidget):
        if widget is not None:
            widget.setMinimumWidth(100)
            widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            doc = QtAds.CDockWidget(widget.windowTitle())
            doc.setWidget(widget)
            doc.setMinimumSizeHintMode(QtAds.CDockWidget.MinimumSizeHintFromContent)
            doc.setMinimumWidth(100)
            self.dock_manager.addAutoHideDockWidget(QtAds.PySide6QtAds.ads.SideBarLocation.SideBarLeft, doc)
            self.viewMenu.addAction(doc.toggleViewAction())

    def addWidgetIntoDock(self, area, widget, allowed_area=QtAds.AllDockAreas):
        if widget is not None:
            doc = QtAds.CDockWidget(widget.windowTitle())
            doc.setWidget(widget)
            self.dock_manager.addDockWidget(area, doc)
            self.viewMenu.addAction(doc.toggleViewAction())

    def new_plot_panel(self) -> TimeSyncPanel:
        return self.central_widget.new_plot_panel()

    def plot_panel(self, name: str):
        return self.central_widget.plot_panel(name)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

    def closeEvent(self, event: QCloseEvent):
        event.accept()
        pipelines.close()

    def push_variables_to_console(self, variables: dict):
        self.console.pushVariables(variable_dict=variables)

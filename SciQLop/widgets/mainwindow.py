from PySide6 import QtCore, QtWidgets, QtGui
from .console import Console
from .products_tree import ProductTree as PyProductTree
from .. import resources
from .central_widget import CentralWidget
from .datetime_range import DateTimeRangeWidgetAction
from .time_sync_panel import TimeSyncPanel
from datetime import datetime, timedelta
from ..backend import TimeRange


class SciQLopMainWindow(QtWidgets.QMainWindow):
    def __init__(self):

        QtWidgets.QMainWindow.__init__(self)
        self._setup_ui()

    def _setup_ui(self):
        default_time_range = TimeRange(datetime.utcnow() - timedelta(days=361),
                                       datetime.utcnow() - timedelta(days=360))
        self.setDockNestingEnabled(True)
        self.central_widget = CentralWidget(self, default_time_range)
        self.setCentralWidget(self.central_widget)
        self.productTree = PyProductTree(self)
        self.productTree.setMinimumWidth(100)
        self.addWidgetIntoDock(QtCore.Qt.LeftDockWidgetArea, self.productTree)
        self.console = Console(parent=self, available_vars={"main_window": self},
                               custom_banner="SciQLop IPython Console ")
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.console)
        self.setWindowTitle("SciQLop")
        self.toolBar = QtWidgets.QToolBar(self)
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, self.toolBar)
        self._dt_range_action = DateTimeRangeWidgetAction(self, default_time_range=default_time_range)
        self.toolBar.addAction(self._dt_range_action)
        self._dt_range_action.range_changed.connect(self.central_widget.set_default_time_range)
        self.addTSPanel = QtGui.QAction(self)
        self.addTSPanel.setIcon(QtGui.QIcon("://icons/add.png"))
        self.addTSPanel.triggered.connect(lambda: self.add_plot_panel(TimeSyncPanel("pan")))
        self.toolBar.addAction(self.addTSPanel)
        self.setWindowIcon(QtGui.QIcon("://icons/SciQLop.png"))
        self.resize(1024, 768)
        self._menubar = QtWidgets.QMenuBar(self)
        self.setMenuBar(self._menubar)
        self._menubar.setGeometry(QtCore.QRect(0, 0, 615, 23))
        self._menubar.setDefaultUp(True)
        self._statusbar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self._statusbar)

    def addWidgetIntoDock(self, area, widget):
        if widget is not None:
            doc = QtWidgets.QDockWidget(self)
            doc.setAllowedAreas(area)
            doc.setWidget(widget)
            self.addDockWidget(area, doc)

    def add_plot_panel(self, panel):
        self.central_widget.add_plot_panel(panel)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

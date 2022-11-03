from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Signal, QMimeData
from PySide6.QtWidgets import QDockWidget, QMainWindow
from .drag_and_drop import DropHandler, DropHelper
from .time_sync_panel import TimeSyncPanel
from ..mime.types import PRODUCT_LIST_MIME_TYPE
from ..mime import decode_mime
from ..backend import TimeRange


class CentralWidget(QtWidgets.QMainWindow):
    panels_list_changed = Signal(list)

    def __init__(self, parent, time_range: TimeRange):
        QMainWindow.__init__(self, parent)
        self.setWindowFlags(QtCore.Qt.WindowType.Widget)
        self.setWindowTitle("Plot area")
        self.setDockNestingEnabled(True)
        self.setMinimumSize(200, 200)
        self._panels = {}
        self._default_time_range = time_range
        self._drop_helper = DropHelper(widget=self,
                                       handlers=[
                                           DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                       callback=self._plot)])

    def _plot(self, mime_data: QMimeData) -> bool:
        assert mime_data.hasFormat(PRODUCT_LIST_MIME_TYPE)
        products = decode_mime(mime_data)
        panel = TimeSyncPanel(name="pan")
        self.add_plot_panel(panel)
        panel.plot(products)
        return True

    def add_plot_panel(self, panel: TimeSyncPanel):
        panel.setXRange(self._default_time_range.to_sciqlopplots_range())
        dw = QDockWidget(self)
        dw.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        dw.setAllowedAreas(QtGui.Qt.DockWidgetArea.AllDockWidgetAreas)
        dw.setWidget(panel)
        panel.setParent(dw)
        self.addDockWidget(QtGui.Qt.DockWidgetArea.TopDockWidgetArea, dw)
        dw.setWindowTitle(panel.name)
        self._panels[panel.name] = panel
        panel.destroyed.connect(lambda: self.remove_panel(panel))
        self.panels_list_changed.emit(self.panels())

    def set_default_time_range(self, time_range: TimeRange):
        self._default_time_range = time_range

    def remove_panel(self, panel: TimeSyncPanel):
        if panel.name in self._panels:
            self._panels.pop(panel.name)
        self.panels_list_changed.emit(self.panels())

    def panels(self):
        return list(self._panels.keys())

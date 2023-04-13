from typing import List

import PySide6QtAds as QtAds
from PySide6.QtCore import Signal, QMimeData, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QWidget, QMainWindow

from .drag_and_drop import DropHandler, DropHelper
from .plots.time_sync_panel import TimeSyncPanel
from ..backend import TimeRange
from ..backend.unique_names import make_simple_incr_name
from ..mime import decode_mime
from ..mime.types import PRODUCT_LIST_MIME_TYPE


class TimeSyncPanelDockWidgetWrapper(QtAds.CDockWidget):
    closed = Signal(str)

    def __init__(self, panel: TimeSyncPanel, parent=None):
        super(TimeSyncPanelDockWidgetWrapper, self).__init__(panel.name)
        self._panel = panel
        self.setWidget(panel)
        panel.destroyed.connect(self._close)

    def _close(self):
        self._panel = None
        self.close()

    @property
    def panel(self):
        return self._panel

    def closeEvent(self, event: QCloseEvent):
        event.accept()
        self.closed.emit(self.windowTitle())
        if self._panel is not None:
            self._panel.delete_node()
        self.deleteLater()


class CentralWidget(QMainWindow):
    panels_list_changed = Signal(list)

    def __init__(self, parent, time_range: TimeRange):
        QMainWindow.__init__(self, parent)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.dock_manager = QtAds.CDockManager(self)
        self.setWindowTitle("Plot area")
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
        panel = self.new_plot_panel()
        panel.plot(products)
        return True

    def plot_panel(self, name: str) -> TimeSyncPanel or None:
        for w in list(filter(lambda w: isinstance(w, TimeSyncPanelDockWidgetWrapper)), self.children()):
            if w.name == name:
                return w.panel

    def new_plot_panel(self) -> TimeSyncPanel:
        panel: TimeSyncPanel = TimeSyncPanel(name=make_simple_incr_name(base="Panel"),
                                             time_range=self._default_time_range)
        panel.time_range = self._default_time_range
        dw = TimeSyncPanelDockWidgetWrapper(panel=panel, parent=self)
        self.dock_manager.addDockWidget(QtAds.DockWidgetArea.TopDockWidgetArea, dw)
        self._panels[panel.name] = panel
        dw.closed.connect(self.remove_panel)
        self.panels_list_changed.emit(self.panels())
        return panel

    def set_default_time_range(self, time_range: TimeRange):
        self._default_time_range = time_range

    def remove_panel(self, panel: TimeSyncPanel or str):
        if type(panel) is str:
            name = panel
        else:
            name = panel.name
        if name in self._panels:
            self._panels.pop(name)
        self.panels_list_changed.emit(self.panels())

    def closeEvent(self, event: QCloseEvent):
        event.accept()
        for p in self._panels.values():
            p.delete_node()

    def panels(self) -> List[str]:
        return list(self._panels.keys())

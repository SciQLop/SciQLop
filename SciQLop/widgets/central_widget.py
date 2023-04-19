from typing import List

import PySide6QtAds as QtAds
from PySide6.QtCore import Signal, QMimeData, Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from .drag_and_drop import DropHandler, DropHelper
from .plots.time_sync_panel import TimeSyncPanel
from ..backend import TimeRange
from ..backend.unique_names import make_simple_incr_name
from ..backend.models import pipelines
from ..mime import decode_mime
from ..mime.types import PRODUCT_LIST_MIME_TYPE


class TimeSyncPanelDockWidgetWrapper(QtAds.CDockWidget):
    closed = Signal(str)

    def __init__(self, name, time_range, parent=None):
        super(TimeSyncPanelDockWidgetWrapper, self).__init__(name)
        panel = TimeSyncPanel(parent=None, name=name,
                              time_range=time_range)
        panel.time_range = time_range
        # self._panel.please_delete_me.connect(self._panel_asked_to_be_deleted)
        self.setWidget(panel)
        panel.delete_me.connect(self.closeDockWidget)
        # self.viewToggled.connect(self._handle_view_toggled)
        self.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)

    @property
    def panel(self) -> TimeSyncPanel:
        return self.widget()

    @property
    def name(self):
        return self.panel.name

    def __del__(self):
        with pipelines.model_update_ctx():
            print('TimeSyncPanelDockWidgetWrapper dtor')
            pipelines.remove_panel(self.panel)


class CentralWidget(QMainWindow):
    panels_list_changed = Signal(list)
    dock_widget_added = Signal(TimeSyncPanelDockWidgetWrapper)

    def __init__(self, parent, time_range: TimeRange):
        QMainWindow.__init__(self, parent)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.dock_manager = QtAds.CDockManager(self)
        self.setWindowTitle("Plot area")
        self.setMinimumSize(200, 200)
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
        widget = self.dock_manager.findDockWidget(name)
        if widget:
            return widget.panel

    def new_plot_panel(self) -> TimeSyncPanel:
        dw = TimeSyncPanelDockWidgetWrapper(name=make_simple_incr_name(base="Panel"),
                                            time_range=self._default_time_range, parent=self)
        self.dock_manager.addDockWidget(QtAds.DockWidgetArea.TopDockWidgetArea, dw)
        self.dock_widget_added.emit(dw)
        self.panels_list_changed.emit(self.panels())
        pipelines.add_add_panel(dw.panel)
        return dw.panel

    def set_default_time_range(self, time_range: TimeRange):
        self._default_time_range = time_range

    def remove_panel(self, panel: TimeSyncPanelDockWidgetWrapper or str):
        print(f"remove_panel {panel}")
        if type(panel) is str:
            dw: TimeSyncPanelDockWidgetWrapper = self.dock_manager.findDockWidget(panel)
        else:
            dw = panel
        dw.release_widget()
        self.dock_manager.removeDockWidget(dw)
        self.panels_list_changed.emit(self.panels())

    def closeEvent(self, event: QCloseEvent):
        event.accept()

    def panels(self) -> List[str]:
        return list(self.dock_manager.dockWidgetsMap().keys())

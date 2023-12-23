from typing import List

import PySide6QtAds as QtAds
from PySide6.QtCore import Signal, QMimeData, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QWidget

from .drag_and_drop import DropHandler, DropHelper
from .plots.abstract_plot_panel import PlotPanel
from .plots.mpl_panel import MPLPanel
from .plots.time_sync_panel import TimeSyncPanel
from ..backend import TimeRange
from ..backend.models import pipelines
from ..backend.unique_names import make_simple_incr_name
from ..mime import decode_mime
from ..mime.types import PRODUCT_LIST_MIME_TYPE


class PanelDockWidgetWrapper(QtAds.CDockWidget):
    closed = Signal(str)

    def __init__(self, panel: PlotPanel):
        super(PanelDockWidgetWrapper, self).__init__(panel.name)
        # self._panel.please_delete_me.connect(self._panel_asked_to_be_deleted)
        self.setWidget(panel)
        panel.delete_me.connect(self.closeDockWidget)
        # self.viewToggled.connect(self._handle_view_toggled)
        self.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)

    @property
    def panel(self) -> PlotPanel:
        return self.widget()

    @property
    def name(self):
        return self.panel.name

    def __del__(self):
        with pipelines.model_update_ctx():
            print('PanelDockWidgetWrapper dtor')
            pipelines.remove_panel(self.panel)


class CentralWidget(QMainWindow):
    panels_list_changed = Signal(list)
    dock_widget_added = Signal(QtAds.CDockWidget)

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
        dw = PanelDockWidgetWrapper(panel=TimeSyncPanel(parent=None, name=make_simple_incr_name(base="Panel"),
                                                        time_range=self._default_time_range))
        tsp: TimeSyncPanel = dw.panel
        tsp.time_range = self._default_time_range
        self.dock_manager.addDockWidget(QtAds.DockWidgetArea.TopDockWidgetArea, dw)
        self.dock_widget_added.emit(dw)
        self.panels_list_changed.emit(self.panels())
        pipelines.add_add_panel(tsp)
        return tsp

    def new_mpl_plot_panel(self) -> MPLPanel:
        dw = PanelDockWidgetWrapper(panel=MPLPanel(parent=None, name=make_simple_incr_name(base="MPLPanel")))
        tsp: MPLPanel = dw.panel
        self.dock_manager.addDockWidget(QtAds.DockWidgetArea.TopDockWidgetArea, dw)
        self.dock_widget_added.emit(dw)
        self.panels_list_changed.emit(self.panels())
        pipelines.add_add_panel(tsp)
        return tsp

    def add_docked_widget(self, widget: QWidget, area: QtAds.DockWidgetArea = QtAds.DockWidgetArea.TopDockWidgetArea):
        dw = QtAds.CDockWidget(widget.windowTitle())
        dw.setWidget(widget)
        self.dock_manager.addDockWidget(area, dw)
        self.dock_widget_added.emit(dw)

    def set_default_time_range(self, time_range: TimeRange):
        self._default_time_range = time_range

    def remove_panel(self, panel: PanelDockWidgetWrapper or str):
        print(f"remove_panel {panel}")
        if type(panel) is str:
            dw: PanelDockWidgetWrapper = self.dock_manager.findDockWidget(panel)
        else:
            dw = panel
        dw.release_widget()
        self.dock_manager.removeDockWidget(dw)
        self.panels_list_changed.emit(self.panels())

    def closeEvent(self, event: QCloseEvent):
        event.accept()

    def panels(self) -> List[str]:
        return list(
            map(lambda dw: dw.name,
                filter(lambda dw: isinstance(dw, PanelDockWidgetWrapper), self.dock_manager.dockWidgets())))

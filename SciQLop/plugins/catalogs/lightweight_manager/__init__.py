from typing import List, Optional

from PySide6.QtCore import Slot, Signal, Qt
from PySide6.QtWidgets import QWidget, QComboBox, QVBoxLayout, QSizePolicy, QCheckBox

from SciQLop.backend import TimeRange
from SciQLop.backend.logging import getLogger
from SciQLop.widgets.mainwindow import SciQLopMainWindow
from SciQLop.widgets.plots.time_span import TimeSpan
from SciQLop.widgets.plots.time_span_controller import TimeSpanController
from SciQLop.widgets.plots.time_sync_panel import TimeSyncPanel
from .catalog_selector import CatalogItem, CatalogSelector
from .event_selector import EventSelector

log = getLogger(__name__)


class PanelSelector(QComboBox):
    panel_selection_changed = Signal(str)

    def __init__(self, parent=None):
        super(PanelSelector, self).__init__(parent)
        self.addItems(["None"])
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.currentTextChanged.connect(self.panel_selection_changed)

    def update_list(self, panels):
        selected = self.currentText()
        self.clear()
        self.addItems(["None"] + panels)
        self.setCurrentText(selected)


class LightweightManager(QWidget):
    update_panels_list = Signal(list)
    current_panel: Optional[TimeSyncPanel] = None
    main_window: SciQLopMainWindow = None
    spans: List[TimeSpan] = []

    def __init__(self, main_window: SciQLopMainWindow, parent=None):
        super().__init__(parent=parent)
        self.setLayout(QVBoxLayout())
        self.main_window = main_window
        self.catalog_selector = CatalogSelector(self)
        self.follow_selected_event = QCheckBox("Jump on selected event", self)
        self.allow_edition = QCheckBox("Allow edition", self)
        self.panel_selector = PanelSelector(self)
        self.event_selector = EventSelector(self)
        self.layout().addWidget(self.panel_selector)
        self.layout().addWidget(self.follow_selected_event)
        self.layout().addWidget(self.allow_edition)
        self.layout().addWidget(self.catalog_selector)
        self.layout().addWidget(self.event_selector)

        self.setWindowTitle("Catalogs")

        self.catalog_selector.catalog_selected.connect(self.catalog_selected)
        self.update_panels_list.connect(self.panel_selector.update_list)
        self.panel_selector.panel_selection_changed.connect(self.panel_selected)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.event_selector.event_selected.connect(self.event_selected)
        self.allow_edition.stateChanged.connect(self._allow_edition_state_change)

        self._time_span_ctrlr: Optional[TimeSpanController] = None

    @Slot()
    def catalog_selected(self, catalogs: List[CatalogItem]):
        events = []
        for c in catalogs:
            events += c.events
        self.event_selector.update_list(events)
        self.update_spans()

    @Slot()
    def event_selected(self, event):
        if self.follow_selected_event.isChecked() and self.current_panel is not None:
            self.current_panel.time_range = TimeRange(event.start.timestamp(), event.stop.timestamp()) * 1.3

    def update_spans(self):
        if self.current_panel is not None:
            self._time_span_ctrlr = TimeSpanController(parent=self, plot_panel=self.current_panel)
            ro = not self.allow_edition.isChecked()
            self.spans = [
                TimeSpan(TimeRange(event.start.timestamp(), event.stop.timestamp()), plot_panel=self.current_panel,
                         visible=False, read_only=ro) for
                event
                in self.event_selector.events]
            self._time_span_ctrlr.set_ranges(self.spans)

    @Slot()
    def panel_selected(self, panel):
        log.debug(f"New panel selected: {panel}")
        self.current_panel = self.main_window.plot_panel(panel)
        self.update_spans()

    @Slot()
    def _allow_edition_state_change(self, state):
        ro = state == Qt.Unchecked
        for s in self.spans:
            s.read_only = ro

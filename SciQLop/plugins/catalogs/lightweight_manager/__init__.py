import os
from typing import List, Optional
from enum import Enum

import tscat
from PySide6.QtCore import Slot, Signal, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QWidget, QComboBox, QVBoxLayout, QSizePolicy, QCheckBox, QGridLayout, QPushButton, \
    QDoubleSpinBox, QLabel

from SciQLop.backend import TimeRange
from SciQLop.backend.sciqlop_logging import getLogger
from SciQLop.widgets.mainwindow import SciQLopMainWindow
from SciQLop.widgets.plots.time_span import TimeSpan
from SciQLop.widgets.plots.time_span_controller import TimeSpanController
from SciQLop.widgets.plots.time_sync_panel import TimeSyncPanel
from .catalog_selector import CatalogItem, CatalogSelector
from .event import Event
from .event_selector import EventSelector
from .event_span import EventSpan

log = getLogger(__name__)


class InteractionMode(Enum):
    Nothing = 0
    Jump = 1
    Edit = 2


class PanelSelector(QComboBox):
    panel_selection_changed = Signal(str)

    def __init__(self, parent=None):
        super(PanelSelector, self).__init__(parent)
        self.addItems(["None"])
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.currentTextChanged.connect(self.panel_selection_changed)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

    def update_list(self, panels):
        selected = self.currentText()
        self.clear()
        self.addItems(["None"] + panels)
        self.setCurrentText(selected)


class LightweightManager(QWidget):
    current_panel: Optional[TimeSyncPanel] = None
    main_window: SciQLopMainWindow = None
    spans: List[TimeSpan] = []

    def __init__(self, main_window: SciQLopMainWindow, parent=None):
        super().__init__(parent=parent)
        self._current_interaction_mode = InteractionMode.Nothing
        self.setLayout(QGridLayout())
        self.main_window = main_window
        self.catalog_selector = CatalogSelector(self)
        self.zoom_factor = QDoubleSpinBox(self)
        self.zoom_factor.setMinimum(0.01)
        self.zoom_factor.setMaximum(100)
        self.zoom_factor.setValue(0.6)
        self.zoom_factor.setSingleStep(0.1)
        self.interaction_mode = QComboBox(self)
        self.interaction_mode.addItems(InteractionMode.__members__.keys())
        self.panel_selector = PanelSelector(self)
        self.event_selector = EventSelector(self)
        self.save_button = QPushButton(self)
        self.save_button.setIcon(QIcon(":/icons/theme/save.png"))
        self.refresh_button = QPushButton(self)
        self.refresh_button.setText("Refresh")
        self.layout().addWidget(self.save_button, 0, 0, 1, 1)
        self.layout().addWidget(self.refresh_button, 0, 1, 1, 1)
        self.layout().addWidget(self.panel_selector, 1, 0, 1, -1)
        self.layout().addWidget(QLabel("Interaction mode", self), 2, 0, 1, 1)
        self.layout().addWidget(self.interaction_mode, 2, 1, 1, -1)
        self.layout().addWidget(QLabel("Zoom factor", self), 3, 0, 1, 1)
        self.layout().addWidget(self.zoom_factor, 3, 1, 1, -1)
        self.layout().addWidget(self.catalog_selector, 5, 0, 1, -1)
        self.layout().addWidget(self.event_selector, 6, 0, 1, -1)

        self.setWindowTitle("Catalogs")

        self.save_button.clicked.connect(self.save)
        self.refresh_button.clicked.connect(self.refresh)
        self.catalog_selector.catalog_selected.connect(self.catalog_selected)
        self.catalog_selector.create_event.connect(self.create_event)
        self.catalog_selector.change_color.connect(self.update_colors)
        self.panel_selector.panel_selection_changed.connect(self.panel_selected)
        self.event_selector.event_selected.connect(self.event_selected)
        self.event_selector.delete_events.connect(self.delete_events)
        self.interaction_mode.currentTextChanged.connect(self._interactions_mode_change)

        self._time_span_ctrlr: Optional[TimeSpanController] = None
        self._last_selected_event: Optional[Event] = None
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(200)

    @Slot()
    def save(self):
        tscat.save()

    @Slot()
    def refresh(self):
        self.event_selector.update_list([])
        self.catalog_selector.update_list()

    @Slot()
    def update_panels_list(self, panels):
        self.panel_selector.update_list(list(map(lambda p: p.name, filter(lambda p: isinstance(p, TimeSyncPanel),
                                                                          map(self.main_window.plot_panel, panels)))))

    @Slot()
    def catalog_selected(self, catalogs: List[CatalogItem]):
        events = []
        for c in catalogs:
            events += [Event(e, c.uuid) for e in c.events]
        self.event_selector.update_list(events)
        self.update_spans()

    @Slot()
    def create_event(self, catalog_uid: str):
        if self.current_panel is not None:
            erange = self.current_panel.time_range * 0.5
            e = tscat.create_event(erange.datetime_start,
                                   erange.datetime_stop,
                                   author=os.getlogin())
            tscat.add_events_to_catalogue(catalogue=self.catalog_selector.catalogs[catalog_uid].tscat_instance,
                                          events=e)
            self.catalog_selector.reload_catalog(catalog_uid)

    @Slot()
    def delete_events(self, events: List[str]):
        if len(events):
            for uuid in events:
                tscat.get_events(tscat.filtering.UUID(uuid))[0].remove(permanently=True)
            self.refresh()

    @Slot()
    def event_selected(self, e: Event):
        if self.current_panel is not None:
            if self._current_interaction_mode == InteractionMode.Jump:
                log.debug(f"event selected {e}, setting panel: {self.current_panel}")
                if e.start == e.stop:
                    self.current_panel.time_range = TimeRange(e.start - 3600, e.stop + 3600)
                else:
                    self.current_panel.time_range = TimeRange(e.start, e.stop) * (1. / self.zoom_factor.value())
                self._last_selected_event = None
            elif self._last_selected_event is None or e.uuid != self._last_selected_event.uuid:
                e.selection_changed.emit(True)
                if self._last_selected_event is not None:
                    self._last_selected_event.selection_changed.emit(False)
                self._last_selected_event = e

    def update_spans(self):
        self._last_selected_event = None
        if self.current_panel is not None:
            if self._time_span_ctrlr is None:
                self._time_span_ctrlr = TimeSpanController(parent=self, plot_panel=self.current_panel)
            ro = self._current_interaction_mode != InteractionMode.Edit
            spans = []
            for e in self.event_selector.events:
                spans.append(EventSpan(e, plot_panel=self.current_panel, visible=False, read_only=ro,
                                       color=self.catalog_selector.color(e.catalog_uid)))
                spans[-1].selected_sig.connect(self.event_selector.select_event)

            self._time_span_ctrlr.spans = spans
            self.current_panel.replot()
        else:
            if self._time_span_ctrlr is not None:
                self._time_span_ctrlr.spans = []
            self._time_span_ctrlr = None

    @Slot()
    def update_colors(self, color: QColor, catalog_uid: str):
        if self.current_panel is not None:
            for e in self.event_selector.events:
                if e.catalog_uid == catalog_uid:
                    e.color_changed.emit(color)
            self.current_panel.replot()

    @Slot()
    def panel_selected(self, panel):
        log.debug(f"New panel selected: {panel}")
        self.current_panel = self.main_window.plot_panel(panel)
        self.update_spans()

    @Slot()
    def _interactions_mode_change(self, mode: str):
        next_mode = InteractionMode[mode]
        if next_mode != self._current_interaction_mode:
            if next_mode == InteractionMode.Edit:
                if self._time_span_ctrlr is not None:
                    for s in self._time_span_ctrlr.spans:
                        s.read_only = False
            if self._current_interaction_mode == InteractionMode.Edit:
                if self._time_span_ctrlr is not None:
                    for s in self._time_span_ctrlr.spans:
                        s.read_only = True
            self._current_interaction_mode = next_mode

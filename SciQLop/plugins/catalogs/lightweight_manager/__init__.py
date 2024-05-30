import os
from typing import List, Optional
from enum import Enum

# import tscat
from tscat_gui import TSCatGUI
from PySide6.QtCore import Slot, Signal, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QWidget, QComboBox, QVBoxLayout, QSizePolicy, QCheckBox, QGridLayout, QPushButton, \
    QDoubleSpinBox, QLabel, QSplitter

from SciQLop.backend import TimeRange
from SciQLop.backend.sciqlop_logging import getLogger
from SciQLop.widgets.mainwindow import SciQLopMainWindow
from SciQLop.widgets.plots.time_span import TimeSpan
from SciQLop.widgets.plots.time_span_controller import TimeSpanController
from SciQLop.widgets.plots.time_sync_panel import TimeSyncPanel
from .catalog_selector import CatalogSelector
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

    def __init__(self, main_window: SciQLopMainWindow, manager_ui: TSCatGUI, parent=None):
        super().__init__(parent=parent)
        self.manager_ui = manager_ui
        self._current_interaction_mode = InteractionMode.Nothing
        self.setLayout(QGridLayout())
        self.main_window = main_window
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.catalog_selector = CatalogSelector(self)
        self.zoom_factor = QDoubleSpinBox(self)
        self.zoom_factor.setMinimum(0.01)
        self.zoom_factor.setMaximum(100)
        self.zoom_factor.setValue(0.6)
        self.zoom_factor.setSingleStep(0.1)
        self.interaction_mode = QComboBox(self)
        self.interaction_mode.addItems(InteractionMode.__members__.keys())
        self.panel_selector = PanelSelector(self)
        self.event_selector = EventSelector(parent=self, manager_ui=manager_ui)
        self.event_selector.event_list_changed.connect(self.update_spans)
        self.save_button = QPushButton(self)
        self.save_button.setIcon(QIcon(":/icons/theme/save.png"))
        self.layout().addWidget(self.save_button, 0, 0, 1, 1)
        self.layout().addWidget(self.panel_selector, 1, 0, 1, -1)
        self.layout().addWidget(QLabel("Interaction mode", self), 2, 0, 1, 1)
        self.layout().addWidget(self.interaction_mode, 2, 1, 1, -1)
        self.layout().addWidget(QLabel("Zoom factor", self), 3, 0, 1, 1)
        self.layout().addWidget(self.zoom_factor, 3, 1, 1, -1)
        self.layout().addWidget(self.vertical_splitter, 5, 0, 1, -1)
        self.vertical_splitter.addWidget(self.catalog_selector)
        self.vertical_splitter.addWidget(self.event_selector)

        self.setWindowTitle("Catalogs")

        self.save_button.clicked.connect(self.save)
        self.panel_selector.panel_selection_changed.connect(self.panel_selected)
        self.catalog_selector.catalog_selection_changed.connect(self.event_selector.catalog_selection_changed)
        self.interaction_mode.currentTextChanged.connect(self._interactions_mode_change)

        self._time_span_ctrlr: Optional[TimeSpanController] = None
        self._last_selected_event: Optional[Event] = None
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(200)

    @Slot()
    def save(self):
        self.manager_ui.save()

    @Slot()
    def update_panels_list(self, panels):
        self.panel_selector.update_list(list(map(lambda p: p.name, filter(lambda p: isinstance(p, TimeSyncPanel),
                                                                          map(self.main_window.plot_panel, panels)))))

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

    @property
    def time_span_ctrlr(self):
        if self._time_span_ctrlr is None and self.current_panel is not None:
            self._time_span_ctrlr = TimeSpanController(parent=self, plot_panel=self.current_panel)
        return self._time_span_ctrlr

    @property
    def has_selected_panel(self):
        return self.current_panel is not None

    def update_spans(self):
        self._last_selected_event = None
        time_span_ctrlr = self.time_span_ctrlr
        if self.has_selected_panel:
            ro = self._current_interaction_mode != InteractionMode.Edit
            spans = []
            for e in self.event_selector.events:
                spans.append(EventSpan(e, plot_panel=self.current_panel, visible=False, read_only=ro,
                                       color=self.catalog_selector.color(e.catalog_uid)))
                spans[-1].selected_sig.connect(self.event_selector.select_event)

            time_span_ctrlr.spans = spans
            self.current_panel.replot()
        else:
            if time_span_ctrlr is not None:
                time_span_ctrlr.spans = []
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
        print(f"New panel selected: {panel}")
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

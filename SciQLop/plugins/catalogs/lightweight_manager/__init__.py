from typing import Dict, Optional, List, Tuple
from enum import Enum
from datetime import datetime

from tscat_gui import TSCatGUI, NewCatalogue
from tscat_gui.tscat_driver.model import tscat_model
from tscat_gui.tscat_driver.actions import CreateEntityAction
from PySide6.QtCore import Slot, Signal, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QWidget, QComboBox, QSizePolicy, QGridLayout, QPushButton, \
    QDoubleSpinBox, QLabel, QSplitter

from SciQLop.backend import TimeRange
from SciQLop.backend.common import combine_colors
from SciQLop.backend.sciqlop_logging import getLogger
from SciQLop.widgets.mainwindow import SciQLopMainWindow
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
        if selected in panels:
            self.setCurrentText(selected)


class LightweightManager(QWidget):
    current_panel: Optional[TimeSyncPanel] = None
    main_window: SciQLopMainWindow = None
    spans: Dict[str, EventSpan] = {}

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
        self.event_selector.event_selected.connect(self.event_selected)
        # self.event_selector.event_start_date_changed.connect(self._event_start_date_changed)
        # self.event_selector.event_stop_date_changed.connect(self._event_stop_date_changed)
        self.save_button = QPushButton(self)
        self.save_button.setIcon(QIcon(":/icons/theme/save.png"))
        self.save_button.setToolTip("Save changes to disk")
        self.add_catalog_button = QPushButton(self)
        self.add_catalog_button.setIcon(QIcon(":/icons/theme/add.png"))
        self.add_catalog_button.setToolTip("Add new catalogue")
        self.layout().addWidget(self.save_button, 0, 0, 1, 1)
        self.layout().addWidget(self.add_catalog_button, 0, 1, 1, 1)
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
        self.add_catalog_button.clicked.connect(self.add_catalog)
        self.panel_selector.panel_selection_changed.connect(self.panel_selected)
        self.catalog_selector.catalog_selection_changed.connect(self.event_selector.catalog_selection_changed)
        self.catalog_selector.create_event.connect(self.create_event)
        self.catalog_selector.change_color.connect(self.update_colors)
        self.interaction_mode.currentTextChanged.connect(self._interactions_mode_change)

        self._time_span_ctrlr: Optional[TimeSpanController] = None
        self._last_selected_event: Optional[Event] = None
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(200)

    def catalogs(self) -> List[str]:
        return self.catalog_selector.catalogs()

    def events(self, catalog: str) -> List[Tuple[datetime, datetime]]:
        from tscat_gui.tscat_driver.model import tscat_model
        from tscat_gui.tscat_driver.catalog_model import CatalogModel
        from tscat_gui.model_base.constants import EntityRole
        from SciQLop.backend.sciqlop_application import sciqlop_app
        from PySide6.QtCore import QThread
        uuid = self.catalog_selector.catalog_uuid(catalog)
        if uuid is not None:
            catalog_model: CatalogModel = tscat_model.catalog(uuid)
            events = []
            # big hack to wait for the model to be loaded
            # the current implementation of the catalog model
            # does not provide a signal or flag to indicate when
            # the model is ready
            for _ in range(5000):
                if catalog_model.rowCount() == 0:
                    sciqlop_app().processEvents()
                    QThread.sleep(1)
                else:
                    break
            for row in range(catalog_model.rowCount()):
                idx = catalog_model.index(row, 0)
                if _event := idx.data(EntityRole):
                    events.append((_event.start, _event.stop))
            return events
        return []

    @Slot()
    def save(self):
        self.manager_ui.save()

    @Slot()
    def add_catalog(self):
        self.manager_ui.state.push_undo_command(NewCatalogue)

    @Slot()
    def update_panels_list(self, panels):
        log.debug(f"Panels list changed: {panels}")
        self.panel_selector.update_list(list(map(lambda p: p.name, filter(lambda p: isinstance(p, TimeSyncPanel),
                                                                          map(self.main_window.plot_panel, panels)))))

    @Slot()
    def create_event(self, catalog_uid: str):
        if self.current_panel is not None:
            time_range: TimeRange = self.current_panel.time_range * 0.5
        else:
            time_range: TimeRange = self.main_window.defaul_range
        self.event_selector.create_event(catalog_uid, time_range.datetime_start(), time_range.datetime_stop())

    def _event_span(self, uuid: str) -> EventSpan or None:
        return self.spans.get(uuid)

    @Slot()
    def _event_start_date_changed(self, uuid: str, date: datetime):
        e = self._event_span(uuid)
        if e is not None:
            e.time_range = TimeRange(date.timestamp(), e.time_range.stop)

    @Slot()
    def _event_stop_date_changed(self, uuid: str, date: datetime):
        e = self._event_span(uuid)
        if e is not None:
            e.time_range = TimeRange(e.time_range.start, date.timestamp())

    @Slot()
    def event_selected(self, uuid: str):
        e = self._event_span(uuid)
        if e is not None:
            if self._current_interaction_mode == InteractionMode.Jump and self.has_selected_panel:
                log.debug(f"event selected {e}, setting panel: {self.current_panel}")
                time_range = e.range
                if time_range.is_empty():
                    self.current_panel.time_range = TimeRange(time_range.start() - 3600, time_range.stop() + 3600)
                else:
                    self.current_panel.time_range = time_range / self.zoom_factor.value()
                self._last_selected_event = None
            elif self._last_selected_event is None or e.uuid != self._last_selected_event.uuid:
                e.selection_changed.emit(True)
                if self._last_selected_event is not None:
                    self._last_selected_event.selection_changed.emit(False)
                self._last_selected_event = e

    @Slot()
    def delete_event(self, uuid: str):
        self.event_selector.delete_events([uuid])

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
            self.spans = {}
            for e in self.event_selector.events:
                span = self._event_span(e.uuid)
                if span is None:
                    span = EventSpan(e, plot_panel=self.current_panel, visible=False, read_only=ro,
                                     color=self.catalog_selector.color(e.catalog_uid))
                    span.selected_sig.connect(self.event_selector.select_event)
                    span.delete_me.connect(self.delete_event)
                    self.spans[e.uuid] = span
                else:
                    span.color = combine_colors(span.color, self.catalog_selector.color(e.catalog_uid))

            time_span_ctrlr.spans = self.spans.values()
            self.current_panel.replot()
        else:
            if time_span_ctrlr is not None:
                time_span_ctrlr.plot_panel = None
                time_span_ctrlr.spans = []
            self._time_span_ctrlr = None

    @Slot()
    def update_colors(self, color: QColor, catalog_uid: str):
        log.debug(f"Color changed: {color}, {catalog_uid}")
        if self.current_panel is not None:
            for span in self.spans.values():
                if span.catalog_uid == catalog_uid:
                    span.color = color
            self.current_panel.replot()

    @Slot()
    def panel_destroyed(self):
        self.current_panel = None
        self._time_span_ctrlr = None

    @Slot()
    def panel_selected(self, panel):
        log.debug(f"New panel selected: {panel}")
        if self.current_panel is not None:
            self.current_panel.destroyed.disconnect(self.panel_destroyed)
        if self._time_span_ctrlr is not None:
            self._time_span_ctrlr.plot_panel = None
            self._time_span_ctrlr.spans = []
        self.current_panel = self.main_window.plot_panel(panel)
        if self.current_panel is not None:
            self.current_panel.destroyed.connect(self.panel_destroyed)
            self.time_span_ctrlr.plot_panel = self.current_panel
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

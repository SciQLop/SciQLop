from typing import List, Optional
import os
from datetime import datetime

from PySide6.QtCore import Signal, QItemSelection, Slot, QItemSelectionModel, QConcatenateTablesProxyModel, \
    QSortFilterProxyModel, QTimer
from PySide6.QtGui import Qt, QKeyEvent
from PySide6.QtWidgets import QComboBox, QListView, QSizePolicy, QTableView, QAbstractItemView

from .event import Event

from tscat_gui.tscat_driver.model import tscat_model, Action, _Event
from tscat_gui.model_base.constants import UUIDDataRole
from tscat_gui.tscat_driver.actions import DeletePermanentlyAction, RestorePermanentlyDeletedAction, SetAttributeAction, \
    _Event, AddEventsToCatalogueAction, CreateEntityAction
from tscat_gui.undo import _EntityBased
from tscat_gui.state import AppState

from SciQLop.backend.sciqlop_logging import getLogger

log = getLogger(__name__)


class CreateEvent(_EntityBased):
    def __init__(self, state: AppState, start, stop, catalog_uuid, parent=None):
        super().__init__(state, parent)
        self.start = start
        self.stop = stop
        self.catalog_uuid = catalog_uuid
        self.setText('Create new Event')

        self.uuid: Optional[str] = None

    def _redo(self):
        def creation_callback(action: CreateEntityAction) -> None:
            self.uuid = action.entity.uuid
            assert self.uuid is not None  # satisfy mypy
            tscat_model.do(AddEventsToCatalogueAction(None,
                                                      [self.uuid], self.catalog_uuid))

        tscat_model.do(CreateEntityAction(creation_callback, _Event,
                                          {
                                              'start': self.start,
                                              'stop': self.stop,
                                              'author': os.getlogin(),
                                              'uuid': self.uuid
                                          }))

    def _undo(self):
        tscat_model.do(DeletePermanentlyAction(None, [self.uuid]))


class DeleteEventsPermanently(_EntityBased):
    def __init__(self, state: AppState, events: List[str], parent=None):
        super().__init__(state, parent)
        self._events = events
        self._deleted_entities: list = []
        self.setText(f'Delete Events permanently')

    def _redo(self):
        def save_deleted_entities(action: DeletePermanentlyAction):
            self._deleted_entities = action.deleted_entities

        tscat_model.do(DeletePermanentlyAction(user_callback=save_deleted_entities, uuids=self._events))

    def _undo(self):
        tscat_model.do(RestorePermanentlyDeletedAction(user_callback=None, deleted_entities=self._deleted_entities))


class EventsModel(QConcatenateTablesProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)

    @Slot()
    def catalog_selection_changed(self, catalogs: List[str]):
        models = set(map(tscat_model.catalog, catalogs))
        sources = set(self.sourceModels())
        for model in sources - models:
            self.removeSourceModel(model)
        for model in models - sources:
            self.addSourceModel(model)


class EventSelector(QTableView):
    event_selected = Signal(object)
    event_list_changed = Signal()
    event_start_date_changed = Signal(str, datetime)
    event_stop_date_changed = Signal(str, datetime)

    def __init__(self, manager_ui, parent=None):
        super().__init__(parent)
        self._selected_catalogs = []
        self._notification_timer = QTimer(self)
        self._notification_timer.setSingleShot(True)
        self._model = EventsModel(parent=self)
        self._manager_ui = manager_ui
        self._sort_model = QSortFilterProxyModel(parent=self)
        self._sort_model.setSourceModel(self._model)
        self.setModel(self._sort_model)
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.selectionModel().selectionChanged.connect(self.event_selection_changed)
        self._notification_timer.timeout.connect(self.event_list_changed)
        self.model().rowsInserted.connect(self._model_changed)
        self.model().rowsRemoved.connect(self._model_changed)
        self.model().modelReset.connect(self._model_changed)
        tscat_model.action_done.connect(self._filter_actions_from_model)

    @Slot()
    def catalog_selection_changed(self, catalogs: List[str]):
        log.debug(f"Catalogs changed: {catalogs}")
        self._selected_catalogs = catalogs
        self._model.catalog_selection_changed(catalogs)
        self.event_list_changed.emit()

    @Slot()
    def _model_changed(self):
        self._notification_timer.start(100)

    @Slot()
    def _filter_actions_from_model(self, action: Action):
        if isinstance(action, SetAttributeAction) and action.name in ('start', 'stop'):
            for value, entity in zip(action.values, action.entities):
                if isinstance(entity, _Event):
                    if action.name == 'start':
                        self.event_start_date_changed.emit(entity.uuid, value)
                    else:
                        self.event_stop_date_changed.emit(entity.uuid, value)

    def _selected_uuids(self) -> List[str]:
        return list(map(lambda idx: idx.data(UUIDDataRole)
                        , self.selectionModel().selectedRows(0)))

    @property
    def events(self) -> List[Event]:
        events = []
        for catalog in self._selected_catalogs:
            model = tscat_model.catalog(catalog)
            for row in range(model.rowCount()):
                idx = model.index(row, 0)
                events.append(Event(idx.data(UUIDDataRole), catalog))
        return events

    def delete_events(self, uuids: List[str]):
        self.selectionModel().clear()
        self._manager_ui.state.push_undo_command(DeleteEventsPermanently, uuids)

    def create_event(self, catalog_uuid: str, start, stop):
        self._manager_ui.state.push_undo_command(CreateEvent, start, stop, catalog_uuid)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            selected_uuids = self._selected_uuids()
            if len(selected_uuids):
                self.delete_events(selected_uuids)
            event.accept()
        else:
            QListView.keyPressEvent(self, event)

    @Slot()
    def event_selection_changed(self, selected: QItemSelection, deselected: QItemSelection):
        selected_uuids = self._selected_uuids()
        if len(selected_uuids):
            self.event_selected.emit(selected_uuids[0])

    @Slot()
    def select_event(self, uuid: str):
        for row in range(self._sort_model.rowCount()):
            idx = self._sort_model.index(row, 0)
            if idx.data(UUIDDataRole) == uuid:
                self.selectionModel().blockSignals(True)
                self.selectionModel().select(idx,
                                             QItemSelectionModel.SelectionFlag.Rows | QItemSelectionModel.SelectionFlag.SelectCurrent)
                self.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)
                self.selectionModel().blockSignals(False)
                break


class PanelSelector(QComboBox):
    def __init__(self, parent=None):
        super(PanelSelector, self).__init__(parent)
        self.addItems(["None"])
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

    def update_list(self, panels):
        selected = self.currentText()
        self.clear()
        self.addItems(["None"] + panels)
        self.setCurrentText(selected)

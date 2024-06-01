from typing import List, Mapping

from PySide6.QtCore import Signal, QItemSelection, Slot, QItemSelectionModel, QConcatenateTablesProxyModel, \
    QAbstractItemModel, QSortFilterProxyModel, QTimer
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel, QKeyEvent
from PySide6.QtWidgets import QComboBox, QListView, QSizePolicy, QTableView, QAbstractItemView

from SciQLop.backend import TimeRange
from .event import Event

from tscat_gui.tscat_driver.model import tscat_model
from tscat_gui.model_base.constants import EntityRole, UUIDDataRole
from tscat_gui.tscat_driver.actions import DeletePermanentlyAction, RestorePermanentlyDeletedAction
from tscat_gui.undo import _EntityBased
from tscat_gui.state import AppState


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
    delete_events = Signal(object)
    event_list_changed = Signal()

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
        self.model().rowsInserted.connect(self._data_changed)
        self.model().rowsRemoved.connect(self._data_changed)
        self.model().modelReset.connect(self._data_changed)

    @Slot()
    def catalog_selection_changed(self, catalogs: List[str]):
        self._selected_catalogs = catalogs
        self._model.catalog_selection_changed(catalogs)

    @Slot()
    def _data_changed(self):
        self._notification_timer.start(100)

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

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            selected_uuids = self._selected_uuids()
            if len(selected_uuids):
                self.selectionModel().clear()
                self._manager_ui.state.push_undo_command(DeleteEventsPermanently, selected_uuids)
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

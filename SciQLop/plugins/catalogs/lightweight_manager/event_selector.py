from typing import List, Mapping

from PySide6.QtCore import Signal, QItemSelection, Slot, QItemSelectionModel, QConcatenateTablesProxyModel, \
    QAbstractItemModel, QSortFilterProxyModel
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel, QKeyEvent
from PySide6.QtWidgets import QComboBox, QListView, QSizePolicy, QTableView, QAbstractItemView

from SciQLop.backend import TimeRange
from .event import Event

from tscat_gui.tscat_driver.model import tscat_model
from tscat_gui.model_base.constants import EntityRole, UUIDDataRole
from tscat_gui.tscat_driver.actions import DeletePermanentlyAction
from tscat_gui.undo import DeletePermanently


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

    def __init__(self, manager_ui, parent=None):
        super().__init__(parent)
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

    @Slot()
    def catalog_selection_changed(self, catalogs: List[str]):
        self._model.catalog_selection_changed(catalogs)

    def _selected_uuids(self) -> List[str]:
        return list(map(lambda idx: idx.data(UUIDDataRole)
                        , self.selectionModel().selectedRows(0)))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            selected_uuids = self._selected_uuids()
            if len(selected_uuids):
                self.selectionModel().clear()
                tscat_model.do(DeletePermanentlyAction(user_callback=None, uuids=selected_uuids))
            event.accept()
        else:
            QListView.keyPressEvent(self, event)

    @Slot()
    def select_event(self, uuid: str):
        pass


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

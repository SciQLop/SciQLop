from typing import List, Mapping

from PySide6.QtCore import Signal, QItemSelection, Slot, QItemSelectionModel, QConcatenateTablesProxyModel, \
    QAbstractItemModel, QSortFilterProxyModel
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel, QKeyEvent
from PySide6.QtWidgets import QComboBox, QListView, QSizePolicy, QTableView, QAbstractItemView

from SciQLop.backend import TimeRange
from .event import Event

from tscat_gui.tscat_driver.model import tscat_model


class EventItem(QStandardItem):
    def __int__(self, *args, **kwargs):
        QStandardItem.__init__(self, *args, **kwargs)

    def set_range(self, new_range: TimeRange):
        self.setText(f"{new_range.datetime_start} -> {new_range.datetime_stop} ")


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = EventsModel(parent=self)
        self._sort_model = QSortFilterProxyModel(parent=self)
        self._sort_model.setSourceModel(self._model)
        self.setModel(self._sort_model)
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # self.selectionModel().selectionChanged.connect(self._event_selected)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

    @Slot()
    def catalog_selection_changed(self, catalogs: List[str]):
        self._model.catalog_selection_changed(catalogs)

    def _selected_uuids(self) -> List[str]:
        return list(map(lambda idx: self._model.itemFromIndex(idx).data(Qt.ItemDataRole.UserRole)
                        , self.selectionModel().selectedIndexes()))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            selected_uuids = self._selected_uuids()
            if len(selected_uuids):
                self.delete_events.emit(selected_uuids)
            event.accept()
        else:
            QListView.keyPressEvent(self, event)

    @Slot()
    def select_event(self, uuid: str):
        selected = self._selected_uuids()
        if len(selected) != 1 or uuid not in selected:
            self.clearSelection()
            self.selectionModel().select(self._model.indexFromItem(self._items[uuid]),
                                         QItemSelectionModel.SelectionFlag.Select)


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

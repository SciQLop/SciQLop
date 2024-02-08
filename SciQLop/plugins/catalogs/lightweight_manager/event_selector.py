from typing import List, Mapping

from PySide6.QtCore import Signal, QItemSelection, Slot, QItemSelectionModel
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel, QKeyEvent
from PySide6.QtWidgets import QComboBox, QListView, QSizePolicy

from SciQLop.backend import TimeRange
from .event import Event


class EventItem(QStandardItem):
    def __int__(self, *args, **kwargs):
        QStandardItem.__init__(self, *args, **kwargs)

    def set_range(self, new_range: TimeRange):
        self.setText(f"{new_range.datetime_start} -> {new_range.datetime_stop} ")


class EventSelector(QListView):
    event_selected = Signal(object)
    delete_events = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QStandardItemModel()
        self.setModel(self._model)
        self._events: Mapping[str, Event] = {}
        self._items: Mapping[str, EventItem] = {}
        self.selectionModel().selectionChanged.connect(self._event_selected)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

    def update_list(self, events: List[Event]):
        self._events = {}
        self._items = {}
        self._model.clear()
        for index, e in enumerate(sorted(events, key=lambda ev: ev.start + (ev.stop - ev.start))):
            item = EventItem()
            item.setData(e.uuid, Qt.ItemDataRole.UserRole)
            item.set_range(e.range)
            e.range_changed.connect(item.set_range)
            self._model.setItem(index, item)
            self._events[e.uuid] = e
            self._items[e.uuid] = item

    def _selected_uuids(self) -> List[str]:
        return list(map(lambda idx: self._model.itemFromIndex(idx).data(Qt.ItemDataRole.UserRole)
                        , self.selectionModel().selectedIndexes()))

    def _event_selected(self, selected: QItemSelection, deselected: QItemSelection):
        indexes = selected.indexes()
        if len(indexes) and len(self._events):
            item = self._model.itemFromIndex(indexes[0])
            self.event_selected.emit(self._events[item.data(Qt.ItemDataRole.UserRole)])

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            selected_uuids = self._selected_uuids()
            if len(selected_uuids):
                self.delete_events.emit(selected_uuids)
            event.accept()
        else:
            QListView.keyPressEvent(self, event)

    @property
    def events(self):
        return self._events.values()

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

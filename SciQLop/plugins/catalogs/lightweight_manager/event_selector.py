from typing import List, Mapping

import tscat
from PySide6.QtCore import Signal, QItemSelection
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QComboBox, QListView


class EventSelector(QListView):
    event_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = QStandardItemModel()
        self.setModel(self.model)
        self._events: Mapping[str, tscat._Event] = {}
        self.selectionModel().selectionChanged.connect(self._event_selected)

    def update_list(self, events: List[tscat._Event]):
        self._events = {}
        self.model.clear()
        for index, event in enumerate(events):
            item = QStandardItem()
            item.setData(event.uuid, Qt.UserRole)
            item.setText(f"{event.start}:{event.stop}")
            self.model.setItem(index, item)
            self._events[event.uuid] = event

    def _event_selected(self, selected: QItemSelection, deselected: QItemSelection):
        indexes = selected.indexes()
        if len(indexes):
            item = self.model.itemFromIndex(indexes[0])
            self.event_selected.emit(self._events[item.data(Qt.UserRole)])

    @property
    def events(self):
        return self._events.values()


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

from typing import List

import tscat
from PySide6.QtCore import QStringListModel
from PySide6.QtWidgets import QComboBox, QListView


class EventSelector(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = QStringListModel()
        self.setModel(self.model)
        self.events: List[tscat._Event] = []

    def update_list(self, events: List[tscat._Event]):
        self.events = events
        self.model.setStringList(list(map(lambda event: f"{event.start}:{event.stop}", events)))


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

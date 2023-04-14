from typing import List

from PySide6.QtCore import Slot, Signal
from PySide6.QtWidgets import QWidget, QComboBox, QVBoxLayout, QSizePolicy

from .catalog_selector import CatalogItem, CatalogSelector
from .event_selector import EventSelector


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


class LightweightManager(QWidget):
    update_panels_list = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setLayout(QVBoxLayout())
        self.catalog_selector = CatalogSelector()
        self.panel_selector = PanelSelector()
        self.event_selector = EventSelector()
        self.layout().addWidget(self.panel_selector)
        self.layout().addWidget(self.catalog_selector)
        self.layout().addWidget(self.event_selector)

        self.setWindowTitle("Catalogs")

        self.catalog_selector.catalog_selected.connect(self.catalog_selected)
        self.update_panels_list.connect(self.panel_selector.update_list)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

    @Slot()
    def catalog_selected(self, catalogs: List[CatalogItem]):
        events = []
        for c in catalogs:
            events += c.events
        self.event_selector.update_list(events)

    @Slot()
    def event_selected(self, event):
        pass

    @Slot()
    def panel_selected(self, panel):
        pass

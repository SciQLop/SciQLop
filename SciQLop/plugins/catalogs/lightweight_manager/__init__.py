from typing import List, Mapping

import tscat
from PySide6.QtCore import Slot, Signal, QStringListModel, QModelIndex, QSize
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QWidget, QComboBox, QVBoxLayout, QListView, QAbstractScrollArea, QSizePolicy


class CatalogItem:
    def __init__(self, catalog: tscat._Catalogue):
        self._tscat_obj = catalog
        self._events = tscat.get_events(self._tscat_obj)

    @property
    def uuid(self):
        return self._tscat_obj.uuid

    @property
    def name(self):
        return self._tscat_obj.name

    @property
    def events(self):
        return self._events

    def __str__(self):
        return self.name


class CatalogSelector(QListView):
    catalog_selected = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = QStandardItemModel()
        self.setModel(self.model)
        self.catalogs: Mapping[str, CatalogItem] = {}
        self.update_list()
        self.clicked.connect(self._catalog_selected)
        self._selected_catalogs = []
        self.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

    def minimumSizeHint(self):
        return QSize(0, 0)

    def _catalog_selected(self, index: QModelIndex):
        item = self.model.itemFromIndex(index)
        selected_catalog = self.catalogs[item.data(Qt.UserRole)]
        if selected_catalog:
            if item.checkState() == Qt.CheckState.Checked:
                self._selected_catalogs.append(selected_catalog)
                self.catalog_selected.emit(self._selected_catalogs)
            else:
                if selected_catalog in self._selected_catalogs:
                    self._selected_catalogs.remove(selected_catalog)
                    self.catalog_selected.emit(self._selected_catalogs)

    def update_list(self):
        self.catalogs = {c.uuid: CatalogItem(c) for c in tscat.get_catalogues()}
        self.model.clear()
        for index, catalog in enumerate(self.catalogs.values()):
            item = QStandardItem()
            item.setData(catalog.uuid, Qt.UserRole)
            item.setText(str(catalog))
            item.setCheckable(True)
            item.setCheckState(Qt.Unchecked)
            self.model.setItem(index, item)


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

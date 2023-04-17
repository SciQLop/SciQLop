from typing import Mapping

import tscat
from PySide6.QtCore import Signal, QModelIndex, QSize
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QListView, QAbstractScrollArea, QSizePolicy


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
                if selected_catalog not in self._selected_catalogs:
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

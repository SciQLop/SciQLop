import logging
from typing import Mapping, Union, List, Any

from PySide6.QtCore import Signal, QModelIndex, QSize, QPersistentModelIndex, QAbstractItemModel, Slot, \
    QAbstractProxyModel, QSortFilterProxyModel, QIdentityProxyModel, QItemSelection
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel, QPainter, QColor, QBrush
from PySide6.QtWidgets import QTreeView, QAbstractScrollArea, QSizePolicy, QPushButton, QHeaderView, \
    QStyledItemDelegate, QWidget, QStyleOptionViewItem, QAbstractItemView, QStyle, QColorDialog


class ExtraColumnsProxyModel(QIdentityProxyModel):
    """A proxy model that adds extra columns to the source model.
    Mostly a Python port of the C++ KExtraColumnsProxyModel class from KDE Frameworks.
    """
    checkStateChanged = Signal(QModelIndex, Qt.CheckState)

    def __init__(self, columns: List[str], first_column_item_checkable=False, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._first_column_item_checkable = first_column_item_checkable
        self._first_column_item_check_state = {}

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return super().columnCount(parent) + len(self._columns)

    def is_extra_column(self, index: QModelIndex) -> bool:
        return index.column() >= self.sourceModel().columnCount()

    def extra_column_data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        raise NotImplementedError

    def set_extra_column_data(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        raise NotImplementedError

    def extra_column_flags(self, index: QModelIndex) -> Qt.ItemFlag:
        raise NotImplementedError

    def set_extra_column_flags(self, index: QModelIndex, flags: Qt.ItemFlag) -> bool:
        raise NotImplementedError

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if self.is_extra_column(index):
            return self.extra_column_data(index, role)
        if index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole and self._first_column_item_checkable:
            return self._first_column_item_check_state.get(index.internalPointer(), Qt.CheckState.Unchecked)
        return self.sourceModel().data(self.mapToSource(index), role)

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if self.is_extra_column(index):
            return self.set_extra_column_data(index, value, role)
        if index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole:
            logging.debug('setData', index, value, role)
            self._first_column_item_check_state[index.internalPointer()] = value
            self.checkStateChanged.emit(index, Qt.CheckState(value))
            return True
        return self.sourceModel().setData(self.mapToSource(index), value, role)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and section >= self.sourceModel().columnCount():
            if role == Qt.ItemDataRole.DisplayRole:
                return self._columns[section - self.sourceModel().columnCount()]
            else:
                return None
        return self.sourceModel().headerData(section, orientation, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if self.is_extra_column(index):
            return self.extra_column_flags(index)
        if index.column() == 0 and self._first_column_item_checkable:
            return self.sourceModel().flags(index) | Qt.ItemFlag.ItemIsUserCheckable
        return self.sourceModel().flags(index)

    def parent(self, index: QModelIndex) -> QModelIndex:
        if self.is_extra_column(index):
            first_col_sibling = self.createIndex(index.row(), 0, index.internalPointer())
            return super().parent(first_col_sibling)
        return super().parent(index)

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if column >= self.sourceModel().columnCount():
            return self.createIndex(row, column, QIdentityProxyModel.index(self, row, 0, parent).internalPointer())
        return super().index(row, column, parent)

    def sibling(self, row, column, idx):
        if row == idx.row() and column == idx.column():
            return idx
        return self.index(row, column, self.parent(idx))

    def buddy(self, proxyIndex: QModelIndex) -> QModelIndex:
        if self.sourceModel() is not None:
            column = proxyIndex.column()
            if column >= self.sourceModel().columnCount():
                return proxyIndex
        return super().buddy(proxyIndex);

    def mapToSource(self, proxyIndex):
        if not proxyIndex.isValid():
            return QModelIndex()
        if self.is_extra_column(proxyIndex):
            return QModelIndex()
        return super().mapToSource(proxyIndex)

    def hasChildren(self, parent=QModelIndex()):
        if parent.column() > 0:
            return False
        return super().hasChildren(parent)

    def mapSelectionToSource(self, selection):
        sourceSelection = QItemSelection()

        if self.sourceModel() is None:
            return sourceSelection

        for index in selection.indexes():
            if not self.is_extra_column(index):
                sourceSelection.append(self.mapToSource(index))
        return sourceSelection

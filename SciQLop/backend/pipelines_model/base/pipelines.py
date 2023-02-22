from contextlib import ContextDecorator
from typing import Dict, Any, Sequence, List

from PySide6.QtCore import QModelIndex, QMimeData, QAbstractItemModel, QStringListModel, QPersistentModelIndex, Qt
from PySide6.QtGui import QIcon

from SciQLop.backend.pipelines_model.base.pipeline_model_item import PipelineModelItem


class _model_change_ctx(ContextDecorator):
    def __init__(self, model: QAbstractItemModel):
        self._model = model

    def __enter__(self):
        self._model.beginResetModel()

    def __exit__(self, exc_type, exc, exc_tb):
        self._model.endResetModel()


class PipelinesModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super(PipelinesModel, self).__init__(parent)
        self._icons: Dict[str, QIcon] = {}
        self._mime_data = None
        self._completion_model = QStringListModel(self)
        self._root = PipelineModelItem('root', None)
        self._last_selected: List[PipelineModelItem] = []

    def model_update_ctx(self):
        return _model_change_ctx(self)

    def add_add_panel(self, panel: PipelineModelItem):
        with self.model_update_ctx():
            self._root.append_child(panel)

    @property
    def completion_model(self):
        return self._completion_model

    def index(self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex = ...) -> QModelIndex:
        if self.hasIndex(row, column, parent):
            if not parent.isValid():
                parent_item = self._root
            else:
                parent_item: PipelineModelItem = parent.internalPointer()
            child_item: PipelineModelItem = parent_item.child_at(row)
            if child_item is not None:
                return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: QModelIndex | QPersistentModelIndex = ...) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        child_item: PipelineModelItem = index.internalPointer()
        parent_item: PipelineModelItem = child_item.parent_item
        if parent_item is not None:
            return self.createIndex(parent_item.row, 0, parent_item)
        return QModelIndex()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            parent_item = self._root
        else:
            parent_item: PipelineModelItem = parent.internalPointer()

        return parent_item.child_count

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        if parent.isValid():
            return parent.internalPointer().column_count
        else:
            return self._root.column_count

    def canFetchMore(self, parent: QModelIndex or QPersistentModelIndex) -> bool:
        if not parent.isValid():
            return False
        item: PipelineModelItem = parent.internalPointer()
        return item.child_count > 0

    def fetchMore(self, parent: QModelIndex or QPersistentModelIndex) -> None:
        pass

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = ...) -> Any:
        if index.isValid():
            item: PipelineModelItem = index.internalPointer()
            if role == Qt.DisplayRole:
                return item.name
            if role == Qt.UserRole:
                return item.name
            if role == Qt.DecorationRole:
                return self._icons.get(item.icon, None)
            if role == Qt.ToolTipRole:
                return ""

    def select(self, indexes: List[QModelIndex | QPersistentModelIndex]):
        if len(self._last_selected):
            list(map(lambda i: i.unselect(), self._last_selected))
        for index in indexes:
            if index.isValid():
                item: PipelineModelItem = index.internalPointer()
                item.select()
                self._last_selected.append(item)
                self._last_selected = list(filter(None.__ne__, self._last_selected))

    def delete(self, indexes: List[QModelIndex | QPersistentModelIndex]):
        self.beginResetModel()
        self._last_selected = []
        for index in indexes:
            if index.isValid():
                item: PipelineModelItem = index.internalPointer()
                if item.child_count:
                    self.delete([self.index(i, index.column(), index) for i in range(item.child_count)])
                item.delete()
        self.endResetModel()

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> int:
        if index.isValid():
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
            item: PipelineModelItem = index.internalPointer()
            flags |= Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
            return flags
        return Qt.NoItemFlags

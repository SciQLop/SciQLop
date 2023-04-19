from contextlib import ContextDecorator
from typing import Dict, Any, Sequence, List, Protocol
from abc import ABCMeta

from PySide6.QtCore import QModelIndex, QMimeData, QAbstractItemModel, QStringListModel, QPersistentModelIndex, Qt, \
    QObject
from PySide6.QtGui import QIcon

from SciQLop.backend.pipelines_model.base.pipeline_node import PipelineModelItem


class RootNodeItemMeta(type(QObject), type(PipelineModelItem)):
    pass


class RootNode(QObject, PipelineModelItem, metaclass=RootNodeItemMeta):
    def __init__(self):
        QObject.__init__(self, None)
        self.setObjectName("root")
        self._children: List['PipelineModelItem'] = []

    @property
    def name(self) -> str:
        return self.objectName()

    @name.setter
    def name(self, new_name: str):
        pass

    @property
    def parent_node(self) -> 'QObject':
        return None

    @parent_node.setter
    def parent_node(self, parent: 'QObject'):
        pass

    @property
    def children_nodes(self) -> List['PipelineModelItem']:
        return self._children

    def index_of(self, child: 'PipelineModelItem') -> int:
        return self.children_nodes.index(child)

    def child_node_at(self, row: int) -> 'PipelineModelItem' or None:
        if 0 <= row < len(self.children_nodes):
            return self.children_nodes[row]
        return None

    def remove_children_node(self, node: 'PipelineModelItem'):
        self._children.remove(node)

    def add_children_node(self, node: 'PipelineModelItem'):
        self._children.append(node)

    @property
    def row(self) -> int:
        if self.parent_node is not None:
            for i, node in enumerate(self.parent_node.children_nodes):
                if self is node:
                    return i
        return 0

    @property
    def child_count(self) -> int:
        return len(self.children_nodes)

    @property
    def column_count(self) -> int:
        return 1

    def select(self):
        pass

    def unselect(self):
        pass

    def delete_node(self):
        for c in self.children_nodes:
            c.delete_node()

    def __eq__(self, other: PipelineModelItem) -> bool:
        return other is self


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
        self._root = RootNode()
        self._last_selected: List[PipelineModelItem] = []

    def model_update_ctx(self):
        return _model_change_ctx(self)

    def add_add_panel(self, panel: PipelineModelItem):
        with self.model_update_ctx():
            panel.parent_node = self._root

    def remove_panel(self, panel: PipelineModelItem):
        with self.model_update_ctx():
            panel.parent_node = None

    @property
    def root_node(self):
        return self._root

    @property
    def completion_model(self):
        return self._completion_model

    def index(self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex = ...) -> QModelIndex:
        if self.hasIndex(row, column, parent):
            if not parent.isValid():
                parent_item = self._root
            else:
                parent_item: PipelineModelItem = parent.internalPointer()  # type: ignore
            child_item: PipelineModelItem = parent_item.children_nodes[row] if row < len(
                parent_item.children_nodes) else None
            if child_item is not None:
                return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: QModelIndex | QPersistentModelIndex = ...) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        child_item: PipelineModelItem = index.internalPointer()  # type: ignore
        parent_item: PipelineModelItem = child_item.parent_node
        if parent_item is not None:
            grand_parent = parent_item.parent_node
            if grand_parent is not None:
                return self.createIndex(grand_parent.children_nodes.index(parent_item), 0, parent_item)
            else:
                return self.createIndex(0, 0, parent_item)
        return QModelIndex()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        if parent.column() > 0:
            return 0

        parent_item: PipelineModelItem = self._root if not parent.isValid() else parent.internalPointer()

        return len(parent_item.children_nodes)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return 1  # type: ignore

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
                item.delete_node()
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

    def close(self):
        self.delete([self.index(0, 0, QModelIndex())])

    def reset(self):
        self.beginResetModel()
        self.endResetModel()

from contextlib import ContextDecorator
from typing import Union, Any, Sequence, List, Optional

from PySide6.QtCore import QModelIndex, QMimeData, QAbstractItemModel, QStringListModel, QPersistentModelIndex, Qt, \
    QObject, Slot, Signal
from PySide6.QtGui import QIcon

from .node import Node, RootNode
from .inspector import build_node, retrieve, update_node
from SciQLop.backend.icons import icons as _icons


class _model_change_ctx(ContextDecorator):
    def __init__(self, model: QAbstractItemModel):
        self._model = model

    def __enter__(self):
        self._model.beginResetModel()

    def __exit__(self, exc_type, exc, exc_tb):
        self._model.endResetModel()


class Model(QAbstractItemModel):
    _last_selected: List[Node] = []
    objects_selected = Signal(list)
    object_deleted = Signal(QObject)

    def __init__(self, parent, root_object: Any):
        super().__init__(parent)
        self._mime_data = None
        self._completion_model = QStringListModel(self)
        self._root = build_node(root_object)
        self._root.changed.connect(self.node_changed)

    @Slot()
    def node_changed(self):
        sender: Node = self.sender()  # type: ignore
        assert (isinstance(sender, Node))
        with self.model_update_ctx():
            update_node(self._retrieve_object(sender), sender, node_changed=self.node_changed)

    def _retrieve_object(self, node: Node) -> Optional[Any]:
        return retrieve(self._root.top_object, node.path)

    def model_update_ctx(self):
        return _model_change_ctx(self)

    @property
    def root_node(self):
        return self._root

    @property
    def completion_model(self):
        return self._completion_model

    def index(self, row: int, column: int,
              parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> QModelIndex:  # type: ignore
        if self.hasIndex(row, column, parent):
            if not parent.isValid():
                parent_item = self._root
            else:
                parent_item = parent.internalPointer()  # type: ignore
            child_item: Node = parent_item.child(row) if row < parent_item.children_count else None
            if child_item is not None:
                return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: Union[QModelIndex, QPersistentModelIndex] = ...) -> QModelIndex:  # type: ignore
        if not index.isValid():
            return QModelIndex()
        child_item: Node = index.internalPointer()  # type: ignore
        parent_item: Optional[Node] = child_item.parent_node
        if parent_item is not None:
            grand_parent = parent_item.parent_node
            if grand_parent is not None:
                return self.createIndex(grand_parent.child_index(parent_item), 0, parent_item)
            else:
                return self.createIndex(0, 0, parent_item)
        return QModelIndex()

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> int:  # type: ignore
        if parent.column() > 0:
            return 0

        parent_item: Node = self._root if not parent.isValid() else parent.internalPointer()

        return parent_item.children_count

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> int:  # type: ignore
        return 1  # type: ignore

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = ...) -> Any:  # type: ignore
        if index.isValid():
            item: Node = index.internalPointer()
            if role == Qt.DisplayRole:
                return item.name
            if role == Qt.UserRole:
                return item.name
            if role == Qt.DecorationRole:
                return _icons.get(item.icon, None)
            if role == Qt.ToolTipRole:
                return ""

    def select(self, indexes: List[Union[QModelIndex, QPersistentModelIndex]]):
        if len(self._last_selected):
            for i in self._last_selected:
                obj = self._retrieve_object(i)
                if obj is not None:
                    obj.unselect()
        objects = []
        for index in indexes:
            if index.isValid():
                item: Node = index.internalPointer()  # type: ignore
                obj = self._retrieve_object(item)
                if obj is not None:
                    objects.append(obj)
                if item.selectable:
                    if obj is not None:
                        obj.select()
                    self._last_selected.append(item)
        self._last_selected = list(filter(None.__ne__, self._last_selected))
        self.objects_selected.emit(objects)

    def delete(self, indexes: List[Union[QModelIndex, QPersistentModelIndex]]):
        self._last_selected = []
        for index in indexes:
            if index.isValid():
                item: Node = index.internalPointer()
                if item is not None and item.deletable:
                    obj = self._retrieve_object(item)
                    if obj is not None:
                        if hasattr(obj, "delete"):
                            obj.delete()
                            self.object_deleted.emit(obj)
                        elif hasattr(obj, "deleteLater"):
                            obj.deleteLater()
                            self.object_deleted.emit(obj)

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        return None

    def flags(self, index: Union[QModelIndex, QPersistentModelIndex]) -> int:
        if index.isValid():
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
            item: Node = index.internalPointer()
            flags |= Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
            return flags
        return Qt.NoItemFlags

    def close(self):
        self.delete([self.index(0, 0, QModelIndex())])

    def reset(self):
        self.beginResetModel()
        self.endResetModel()

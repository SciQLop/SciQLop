from typing import Dict, List, Any
from PySide6.QtCore import QModelIndex, QAbstractItemModel, QStringListModel, QPersistentModelIndex, Qt
from PySide6.QtGui import QIcon


class ProductNode:
    def __init__(self, name: str, metadata: Dict[str, str], parent: 'ProductNode' = None, is_parameter=False):
        self._metadata = metadata
        self._name = name
        self._children = []
        self._parent = parent
        self._is_param = is_parameter

    def append_child(self, child: 'ProductNode'):
        child.set_parent(self)
        self._children.append(child)

    def set_parent(self, parent: 'ProductNode'):
        if self._parent is None:
            self._parent = parent
        else:
            raise ValueError("Can't set parent when one is already set")

    @property
    def is_parameter(self):
        return self._is_param

    @property
    def metadata(self):
        return self._metadata

    @property
    def children(self) -> List['ProductNode']:
        return self._children

    @property
    def parent(self) -> 'ProductNode' or None:
        return self._parent

    @property
    def name(self):
        return self._name

    def index_of(self, child: 'ProductNode'):
        return self._children.index(child)

    @property
    def icon(self):
        return ""

    @property
    def row(self) -> int:
        if self._parent is not None:
            return self._parent.index_of(self)
        return 0

    def child(self, row: int) -> 'ProductNode' or None:
        if 0 <= row < len(self._children):
            return self._children[row]
        return None

    @property
    def child_count(self) -> int:
        return len(self._children)

    @property
    def column_count(self) -> int:
        return 1


def for_all_nodes(f, node):
    f(node)
    for child in node.children:
        for_all_nodes(f, child)


def _make_completion_list(node: ProductNode):
    return [f"name: {node.name}"] + [f"{key}: {value}" for key, value in node.metadata.items()]


class ProductsModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super(ProductsModel, self).__init__(parent)
        self._icons: Dict[str, QIcon] = {}
        self._completion_model = QStringListModel(self)
        self._root = ProductNode(name="root", metadata={})

    @property
    def completion_model(self):
        return self._completion_model

    def add_products(self, products: ProductNode):
        self.beginResetModel()
        self._root.append_child(child=products)
        self.endResetModel()
        self._update_completion(products)

    def _update_completion(self, products: ProductNode):
        strings = set()
        for_all_nodes(lambda node: strings.update(_make_completion_list(node)), products)
        strings.update(set(self._completion_model.stringList()))
        self._completion_model.setStringList(list(strings))

    def index(self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex = ...) -> QModelIndex:
        if self.hasIndex(row, column, parent):
            if not parent.isValid():
                parent_item = self._root
            else:
                parent_item: ProductNode = parent.internalPointer()
            child_item: ProductNode = parent_item.child(row)
            if child_item is not None:
                return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: QModelIndex | QPersistentModelIndex = ...) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        child_item: ProductNode = index.internalPointer()
        parent_item: ProductNode = child_item.parent

        if parent_item is self._root:
            return QModelIndex()

        return self.createIndex(parent_item.row, 0, parent_item)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            parent_item = self._root
        else:
            parent_item: ProductNode = parent.internalPointer()

        return parent_item.child_count

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        if parent.isValid():
            return parent.internalPointer().column_count
        else:
            return self._root.column_count

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return None
        item: ProductNode = index.internalPointer()
        if role == Qt.DisplayRole:
            return item.name
        if role == Qt.UserRole:
            return f"name: {item.name}" + "\n".join([f"{key}: {value}" for key, value in item.metadata.items()])
        if role == Qt.DecorationRole:
            return self._icons.get(item.icon, None)
        if role == Qt.ToolTipRole:
            return "<br/>".join([f"<b>{key}:</b> {value}" for key, value in item.metadata.items()])

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> int:
        if index.isValid():
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
            item: ProductNode = index.internalPointer()
            if item.is_parameter:
                flags |= Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
            return flags
        return Qt.NoItemFlags

import pickle
from typing import Dict, List, Any
from typing import Sequence

from PySide6.QtCore import QModelIndex, QMimeData, QAbstractItemModel, QStringListModel, QPersistentModelIndex, Qt
from PySide6.QtGui import QIcon

from SciQLop.mime import register_mime, encode_mime
from SciQLop.mime.types import PRODUCT_LIST_MIME_TYPE
from .product_node import ProductNode


def for_all_nodes(f, node):
    f(node)
    for child in node.children:
        for_all_nodes(f, child)


def _make_completion_list(product: ProductNode):
    return [f"name: {product.name}"] + [f"{key}: {value}" for key, value in product.metadata.items()]


class ProductsModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super(ProductsModel, self).__init__(parent)
        self._icons: Dict[str, QIcon] = {}
        self._mime_data = None
        self._completion_model = QStringListModel(self)
        self._root = ProductNode(name="root", metadata={}, uid='root', provider="")

    @property
    def completion_model(self):
        return self._completion_model

    def product(self, path: str) -> ProductNode or None:
        p = self._root
        for element in path.split('/'):
            if p is not None:
                p = p[element]
        if p is not None:
            return p

    def add_products(self, products: ProductNode):
        self.beginResetModel()
        self._root.append_child(child=products)
        self.endResetModel()
        self._update_completion(products)

    def _update_completion(self, products: ProductNode):
        strings = set()
        for_all_nodes(lambda node: strings.update(_make_completion_list(node)), products)
        strings.update(set(self._completion_model.stringList()))
        self._completion_model.setStringList(sorted(list(strings)))

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

    def canFetchMore(self, parent: QModelIndex or QPersistentModelIndex) -> bool:
        if not parent.isValid():
            return False
        item: ProductNode = parent.internalPointer()
        return item.child_count > 0

    def fetchMore(self, parent: QModelIndex or QPersistentModelIndex) -> None:
        pass

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return None
        item: ProductNode = index.internalPointer()
        if role == Qt.DisplayRole:
            return item.name
        if role == Qt.UserRole:
            return item.str
        if role == Qt.DecorationRole:
            return self._icons.get(item.icon, None)
        if role == Qt.ToolTipRole:
            return "<br/>".join(
                [f"<b>{key}:</b> {value}" for key, value in item.metadata.items() if not key.startswith('__')])

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        products = list(filter(lambda index: index.is_parameter,
                               map(lambda index: index.internalPointer(), indexes)))
        self._mime_data = encode_mime(products)
        return self._mime_data

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> int:
        if index.isValid():
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
            item: ProductNode = index.internalPointer()
            if item.is_parameter:
                flags |= Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
            return flags
        return Qt.NoItemFlags


def _mime_encode_product_list(products: List[ProductNode]) -> QMimeData:
    mdata = QMimeData()
    mdata.setData(PRODUCT_LIST_MIME_TYPE, pickle.dumps(list(map(lambda p: p.copy(), products))))
    mdata.setText(":".join(list(map(lambda p: f"{p.provider}/{p.uid}", products))))
    return mdata


def _mime_decode_product_list(mime_data: QMimeData) -> List[ProductNode] or None:
    if PRODUCT_LIST_MIME_TYPE in mime_data.formats():
        return pickle.loads(mime_data.data(PRODUCT_LIST_MIME_TYPE))
    return None


register_mime(obj_type=list, mime_type=PRODUCT_LIST_MIME_TYPE, nested_type=ProductNode,
              encoder=_mime_encode_product_list,
              decoder=_mime_decode_product_list)
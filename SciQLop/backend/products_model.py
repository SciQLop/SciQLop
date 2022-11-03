from typing import Dict, List, Any
from enum import Enum
from PySide6.QtCore import QModelIndex, QMimeData, QAbstractItemModel, QStringListModel, QPersistentModelIndex, Qt
from PySide6.QtGui import QIcon
from typing import Sequence
from ..mime import register_mime, encode_mime
from ..mime.types import PRODUCT_LIST_MIME_TYPE
import pickle


class ParameterType(Enum):
    NONE = 0
    SCALAR = 1
    VECTOR = 2
    MULTICOMPONENT = 3
    SPECTROGRAM = 4


class Product:
    __slots__ = ["_metadata", "_name", "_children", "_is_param", "_str_content", "_provider", "_uid", "_parameter_type"]

    def __init__(self, name: str, uid: str, provider: str, metadata: Dict[str, str], is_parameter=False,
                 parameter_type: ParameterType = ParameterType.NONE):
        self._metadata = metadata
        self._name = name
        self._is_param = is_parameter
        self._provider = provider
        self._uid = uid
        self._parameter_type = parameter_type
        self._str_content = f"name: {name}" + "\n".join([f"{key}: {value}" for key, value in metadata.items()])

    @property
    def is_parameter(self) -> bool:
        return self._is_param

    @property
    def parameter_type(self) -> ParameterType:
        return self._parameter_type

    @property
    def metadata(self) -> Dict[str, str]:
        return self._metadata

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider(self):
        return self._provider

    @property
    def uid(self):
        return self._uid

    @property
    def str(self):
        return self._str_content


class ProductNode:
    __slots__ = ["_children", "_parent", "_product"]

    def __init__(self, name: str, uid: str, provider: str, metadata: Dict[str, str], parent: 'ProductNode' = None,
                 is_parameter=False, parameter_type: ParameterType = ParameterType.NONE):
        self._parent = parent
        self._children = []
        self._product = Product(name, uid, provider, metadata, is_parameter, parameter_type)

    def append_child(self, child: 'ProductNode'):
        child.set_parent(self)
        self._children.append(child)

    def set_parent(self, parent: 'ProductNode'):
        if self._parent is None:
            self._parent = parent
        else:
            raise ValueError("Can't set parent when one is already set")

    @property
    def children(self) -> List['ProductNode']:
        return self._children

    @property
    def parent(self) -> 'ProductNode' or None:
        return self._parent

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

    @property
    def product(self) -> Product:
        return self._product


def for_all_nodes(f, node):
    f(node)
    for child in node.children:
        for_all_nodes(f, child)


def _make_completion_list(product: Product):
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

    def add_products(self, products: ProductNode):
        self.beginResetModel()
        self._root.append_child(child=products)
        self.endResetModel()
        self._update_completion(products)

    def _update_completion(self, products: ProductNode):
        strings = set()
        for_all_nodes(lambda node: strings.update(_make_completion_list(node.product)), products)
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

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return None
        item: ProductNode = index.internalPointer()
        if role == Qt.DisplayRole:
            return item.product.name
        if role == Qt.UserRole:
            return item.product.str
        if role == Qt.DecorationRole:
            return self._icons.get(item.icon, None)
        if role == Qt.ToolTipRole:
            return "<br/>".join(
                [f"<b>{key}:</b> {value}" for key, value in item.product.metadata.items() if not key.startswith('__')])

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        products = list(filter(lambda index: index.is_parameter,
                               map(lambda index: index.internalPointer().product, indexes)))
        self._mime_data = encode_mime(products)
        return self._mime_data

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> int:
        if index.isValid():
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
            item: ProductNode = index.internalPointer()
            if item.product.is_parameter:
                flags |= Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
            return flags
        return Qt.NoItemFlags


def _mime_encode_product_list(products: List[Product]) -> QMimeData:
    mdata = QMimeData()
    mdata.setData(PRODUCT_LIST_MIME_TYPE, pickle.dumps(products))
    mdata.setText(":".join(list(map(lambda p: f"{p.provider}/{p.uid}", products))))
    return mdata


def _mime_decode_product_list(mime_data: QMimeData) -> List[Product] or None:
    if PRODUCT_LIST_MIME_TYPE in mime_data.formats():
        return pickle.loads(mime_data.data(PRODUCT_LIST_MIME_TYPE))
    return None


register_mime(obj_type=list, mime_type=PRODUCT_LIST_MIME_TYPE, nested_type=Product,
              encoder=_mime_encode_product_list,
              decoder=_mime_decode_product_list)

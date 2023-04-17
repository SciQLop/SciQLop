import bisect
from typing import List, Dict

from ..enums import ParameterType


class ProductNode:
    __slots__ = ["_children", "_parent", "_metadata", "_name", "_is_param", "_str_content", "_provider", "_uid",
                 "_parameter_type"]

    def __init__(self, name: str, uid: str, provider: str, metadata: Dict[str, str], is_parameter=False,
                 parameter_type: ParameterType = ParameterType.NONE, parent: 'ProductNode' = None):
        self._parent = parent
        self._children = []
        self._metadata = metadata
        self._name = name
        self._is_param = is_parameter
        self._provider = provider
        self._uid = uid
        self._parameter_type = parameter_type
        self._str_content = f"name: {name}" + "\n".join([f"{key}: {value}" for key, value in metadata.items()])
        # self._product = Product(name, uid, provider, metadata, is_parameter, parameter_type)

    def copy(self):
        return ProductNode(name=self.name, uid=self.uid, provider=self.provider, metadata=self.metadata,
                           is_parameter=self.is_parameter, parameter_type=self.parameter_type, parent=None)

    def append_child(self, child: 'ProductNode'):
        child.set_parent(self)
        bisect.insort(self._children, child, key=lambda c: c.name)

    def set_parent(self, parent: 'ProductNode'):
        if self._parent is None:
            self._parent = parent
        else:
            raise ValueError("Can't set parent when one is already set")

    def __getitem__(self, item: str) -> "ProductNode" or None:
        return next(iter(filter(lambda n: n.name == item, self._children)), None)

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
    def is_parameter(self) -> bool:
        return self._is_param

    @property
    def parameter_type(self) -> ParameterType:
        return self._parameter_type

    @property
    def metadata(self) -> Dict[str, str or List[str]]:
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

    @property
    def path(self):
        if self._parent:
            parent_path = self._parent.path
            if parent_path != "":
                return self.parent.path + "/" + self.name
        return self.name

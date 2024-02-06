from ..common import insort
from typing import List, Dict, Optional

from ..enums import ParameterType


class ProductNode:
    __slots__ = ["_children", "_parent", "_metadata", "_name", "_is_param", "_str_content", "_provider", "_uid",
                 "_parameter_type", "_icon", "_deletable"]

    def __init__(self, name: str, uid: str, provider: str, metadata: Dict[str, str], is_parameter=False,
                 parameter_type: ParameterType = ParameterType.NONE, parent: Optional['ProductNode'] = None,
                 icon: Optional[str] = None, deletable: bool = False):
        self._parent = parent
        self._children = []
        self._metadata = metadata
        self._name = name
        self._is_param = is_parameter
        self._provider = provider
        self._uid = uid
        self._parameter_type = parameter_type
        self._str_content = f"name: {name}" + "\n".join([f"{key}: {value}" for key, value in metadata.items()])
        self._icon = icon or ""
        self._deletable = deletable

    def copy(self):
        return ProductNode(name=self.name, uid=self.uid, provider=self.provider, metadata=self.metadata,
                           is_parameter=self.is_parameter, parameter_type=self.parameter_type, parent=None)

    def merge(self, child: 'ProductNode', overwrite_leaves=False) -> "ProductNode":
        """Merge a child node into this one, if the child is a leaf and already exists in this node's children plus
        overwrite_leaves is True, it is overwritten, otherwise it is ignored. If the child is not a leaf, it is merged.

        Parameters
        ----------
        child: ProductNode
            The node to merge into this one
        overwrite_leaves: bool
            If True, when the child is a leaf and already exists in this node's children, it is overwritten, otherwise it
            is ignored

        """
        if child.name in self:
            if len(child.children) == 0 and overwrite_leaves and child is not self[child.name]:
                self.remove_child(child.name)
                self.append_child(child)
            else:
                for sub_child in child.children:
                    self[child.name].merge(sub_child)
        else:
            self.append_child(child)
        return child

    def append_child(self, child: 'ProductNode') -> "ProductNode":
        child.set_parent(self)
        insort(self._children, child, key=lambda n: n.name)
        return child

    def remove_child(self, name: str):
        child = self[name]
        if child is not None:
            self._children.remove(child)
            child._parent = None

    def set_parent(self, parent: 'ProductNode'):
        if self._parent is None:
            self._parent = parent
        else:
            raise ValueError("Can't set parent when one is already set")

    def __getitem__(self, item: str) -> "ProductNode" or None:
        return next(iter(filter(lambda n: n.name == item, self._children)), None)

    def __contains__(self, item: str) -> bool:
        return any(map(lambda n: n.name == item, self._children))

    @property
    def children(self) -> List['ProductNode']:
        return self._children

    @property
    def parent(self) -> 'ProductNode' or None:
        return self._parent

    @property
    def is_deletable(self) -> bool:
        return self._deletable

    def index_of(self, child: 'ProductNode'):
        return self._children.index(child)

    @property
    def icon(self):
        return self._icon

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

from typing import Dict, Any, Sequence, List, Optional
from enum import Flag, auto
from PySide6.QtCore import QObject, Signal, Slot, Property


def prepend_to_each(s: str, l: Sequence[str], last=None) -> List[str]:
    if last is not None and len(l) > 0:
        return [s + e for e in l[:-1]] + [last + l[-1]]
    return [s + e for e in l]


class NodeCapabilities(Flag):
    none = 0
    selectable = auto()
    deletable = auto()


class Node(QObject):
    changed = Signal()

    _icon: str = ""
    _name: str = ""
    _children: List['Node'] = []
    _parent: Optional['Node'] = None
    _bound_id: int = -1
    _capabilities: NodeCapabilities = NodeCapabilities.none

    def __init__(self, name, bound_object: Any, parent: Optional['Node'] = None, icon="",
                 children: Optional[List['Node']] = None):
        super().__init__()
        self._parent = parent
        self._name = name
        self._icon = icon
        self._children = children or []
        for child in self._children:
            child._parent = self
        self._bound_id = id(bound_object)
        if hasattr(bound_object, "select") and hasattr(bound_object, "unselect"):
            self._capabilities |= NodeCapabilities.selectable

        if hasattr(bound_object, "deleteLater") or hasattr(bound_object, "delete"):
            self._capabilities |= NodeCapabilities.deletable

    def __eq__(self, other) -> bool:
        if isinstance(other, Node):
            return self._bound_id == other._bound_id
        return False

    @property
    def selectable(self):
        return NodeCapabilities.selectable in self._capabilities

    @property
    def deletable(self):
        return NodeCapabilities.deletable in self._capabilities

    def has(self, obj: Any) -> bool:
        obj_id = id(obj)
        return any([obj_id == c._bound_id for c in self._children])

    def add_child_node(self, node: 'Node'):
        self._children.append(node)
        node._parent = self

    def remove_child_node(self, node: 'Node'):
        self._children.remove(node)
        node._parent = None

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, new_name: str):
        self._name = new_name

    @property
    def parent_node(self) -> Optional['Node']:
        return self._parent

    @property
    def children_nodes(self) -> List['Node']:
        return self._children

    @property
    def bound_id(self) -> int:
        return self._bound_id

    @property
    def children_count(self) -> int:
        return len(self._children)

    def child(self, row: int) -> Optional['Node']:
        if 0 <= row < len(self._children):
            return self._children[row]
        return None

    def child_index(self, child: 'Node') -> int:
        return self._children.index(child)

    @property
    def icon(self) -> str:
        return self._icon

    @icon.setter
    def icon(self, icon: str):
        self._icon = icon

    @property
    def path(self):
        # could optimize this by caching the path and updating it on parent change
        p = [self.name]
        node = self.parent_node
        while node is not None:
            p.append(node.name)
            node = node.parent_node
        return list(reversed(p))

    def _shifted_repr(self, prefix="  ├──", last_prefix="  └──"):
        return f"""{self.name}:
{''.join(prepend_to_each(prefix, ([c._shifted_repr(f"  │{prefix}", f"  │{last_prefix}") for c in self._children]), last_prefix))}"""

    def __repr__(self):
        return self._shifted_repr()


class RootNode(Node):
    def __init__(self, top_obj: QObject):
        super().__init__(top_obj.objectName(), bound_object=top_obj, parent=None, icon="", children=[])
        self._top_obj = top_obj

    @property
    def top_object(self) -> Any:
        return self._top_obj

from typing import Dict, Callable, Any, Optional, Protocol, List
from PySide6.QtCore import QObject, Signal, Slot, Property
from ..backend import filter_none
from .node import Node


class Inspector(Protocol):

    @staticmethod
    def list_children(obj: Any) -> List[Any]:
        ...

    @staticmethod
    def child(obj: Any, name: str) -> Optional[Any]:
        ...

    @staticmethod
    def build_node(obj: Any, parent: Optional[Node] = None, children: Optional[List[Node]] = None) -> Optional[Node]:
        ...


class DummyInspector(Inspector):

    @staticmethod
    def build_node(obj: Any, parent: Optional[Node] = None, children: Optional[List[Node]] = None) -> Optional[Node]:
        return None

    @staticmethod
    def list_children(obj: Any) -> List[Any]:
        return []

    @staticmethod
    def child(obj: Any, name: str) -> Optional[Any]:
        return None


__inspectors__: Dict[str, Inspector] = {}


def register_inspector(cls: type):
    def _(inspector: Inspector):
        __inspectors__[cls.__name__] = inspector
        return inspector

    return _


def find_inspector(obj: Any) -> Inspector:
    def inner_find_inspector(cls: type) -> Inspector:
        inspector = __inspectors__.get(cls.__name__, DummyInspector)
        if inspector is DummyInspector and cls.__base__ is not None:
            return inner_find_inspector(cls.__base__)
        else:
            return inspector

    return inner_find_inspector(type(obj))


def build_node(obj: Any, parent: Optional[Node] = None, node_changed: Optional[Callable] = None) -> Optional[Node]:
    inspector = find_inspector(obj)
    node = inspector.build_node(obj, parent=parent,
                                children=filter_none([build_node(c, obj) for c in inspector.list_children(obj)]))
    if node is not None:
        node.changed.connect(node_changed)
    return node


def update_node(obj: Any, node: Node, node_changed: Optional[Callable] = None) -> None:
    inspector = find_inspector(obj)
    children = inspector.list_children(obj)
    children_ids = set(map(id, children))
    node_children_ids = set(map(lambda n: n.bound_id, node.children_nodes))

    for c in children:
        if id(c) not in node_children_ids:
            child = build_node(c, parent=node, node_changed=node_changed)
            if child is not None:
                node.add_child_node(child)

    for c in node.children_nodes:
        if c.bound_id not in children_ids:
            node.remove_child_node(c)


def retrieve(obj: Any, path: List[str]) -> Optional[Any]:
    name = path[-1]
    if len(path) > 0:
        path = path[1:]
        for p in path:
            obj = find_inspector(obj).child(obj, p)
            if obj is None:
                return None
        if obj.name == name:
            return obj
    return None

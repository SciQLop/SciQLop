from typing import List, Optional

from PySide6.QtCore import QObject, Slot

from .base import model
from .base.pipeline_node import PipelineModelItem
from .. import logging

log = logging.getLogger(__name__)

_nodes: List['QObjectNode'] = []


class QObjectNodeMeta(type(QObject), type(PipelineModelItem)):
    pass


class QObjectNode(PipelineModelItem, QObject, metaclass=QObjectNodeMeta):
    _wrapped_object: Optional[QObject] = None
    _wrapped_class_name: str = ""

    def __init__(self, wrapped_object: Optional[QObject], parent: 'QObjectNode' or object):
        QObject.__init__(self)
        with model.model_update_ctx():
            if not isinstance(parent, PipelineModelItem):
                parent = QObjectNode._find_node(parent)
            if parent is not None:
                self.parent_node = parent
            else:
                raise ValueError("Can't find any valid parent node")
        if wrapped_object:
            self.wrapped_object = wrapped_object

    @staticmethod
    def _find_node(wrapped_object):
        for n in _nodes:
            if id(wrapped_object) == id(n._wrapped_object):
                return n

    def _update_wrapped_object(self):
        if self._wrapped_object is not None:
            if hasattr(self._wrapped_object, 'model_please_delete_me'):
                self._wrapped_object.model_please_delete_me.connect(self.delete_node)
            self._wrapped_class_name = self._wrapped_object.__class__.__name__
            log.info(f"Setting wrapped object {self._wrapped_class_name}:{self._wrapped_object}")
            self._wrapped_object.destroyed.connect(self._wrapped_object_deleted)

    @property
    def wrapped_object(self):
        return self._wrapped_object

    @wrapped_object.setter
    def wrapped_object(self, obj):
        if self._wrapped_object is not None:
            raise ValueError("Wrapped object already set")
        self._wrapped_object = obj
        self._update_wrapped_object()

    @Slot()
    def _wrapped_object_deleted(self):
        _nodes.remove(self)
        self._wrapped_object = None
        self.delete_node()

    @property
    def name(self) -> str:
        if self._wrapped_object is None:
            return "Object already deleted"
        return self._wrapped_object.objectName()

    @name.setter
    def name(self, new_name: str):
        self._wrapped_object.setObjectName(new_name)

    @property
    def parent_node(self) -> 'QObjectNode':
        return self.parent()

    @parent_node.setter
    def parent_node(self, parent: 'QObjectNode'):
        self.setParent(parent)

    @property
    def children_nodes(self) -> List['QObjectNode']:
        return list(filter(lambda n: isinstance(n, QObjectNode), self.children()))

    def index_of(self, child: 'QObjectNode') -> int:
        return self.children_nodes.index(child)

    def child_node_at(self, row: int) -> 'QObjectNode' or None:
        if 0 <= row < len(self.children_nodes):
            return self.children_nodes[row]
        return None

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
        if hasattr(self._wrapped_object, 'select'):
            self._wrapped_object.select()

    def unselect(self):
        if hasattr(self._wrapped_object, 'unselect'):
            self._wrapped_object.unselect()

    def _cleanup(self):
        if self in _nodes:
            _nodes.remove(self)
        if self._wrapped_object:
            with model.model_update_ctx():
                log.debug(f"deleting node {type(self)}:{self.name}")
                self._wrapped_object.destroyed.disconnect(self._wrapped_object_deleted)
                if hasattr(self._wrapped_object, 'model_please_delete_me'):
                    self._wrapped_object.model_please_delete_me.disconnect(self.delete_node)
                if hasattr(self._wrapped_object, 'please_delete_me'):
                    self._wrapped_object.please_delete_me.emit(self._wrapped_object)
                else:
                    self._wrapped_object.deleteLater()
                self._wrapped_object = None

    def delete_node(self):
        self._cleanup()
        with model.model_update_ctx():
            self.setParent(None)
        self.deleteLater()

    def __del__(self):
        self._cleanup()
        log.info(f"Deleting {self._wrapped_class_name}: {id(self):08x}")

    def __eq__(self, other: PipelineModelItem) -> bool:
        if other is not None:
            return self.parent_node == other.parent_node and self.row == other.row
        return False


def auto_register(cls):
    def new_ctor(self, *args, **kwargs):
        with model.model_update_ctx():
            self.___init___(*args, **kwargs)
            if hasattr(self, 'destroyed'):
                self.destroyed.connect(model.reset)

    cls.___init___ = cls.__init__
    cls.__init__ = new_ctor
    return cls

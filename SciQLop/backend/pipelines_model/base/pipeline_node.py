from abc import ABC, abstractmethod, ABCMeta
from typing import List

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from ... import logging

log = logging.getLogger(__name__)


class PipelineModelItem(ABC):

    def __init__(self):
        pass

    def __del__(self):
        log.info(f"Deleting {self.__class__.__name__}: {id(self):08x}")

    def __eq__(self, other: 'PipelineModelItem') -> bool:
        if other is not None:
            return self.parent_node == other.parent_node and self.row == other.row
        return False

    @property
    def icon(self) -> str:
        return ""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @name.setter
    @abstractmethod
    def name(self, new_name: str):
        ...

    @property
    @abstractmethod
    def parent_node(self) -> 'PipelineModelItem':
        ...

    @parent_node.setter
    @abstractmethod
    def parent_node(self, parent: 'PipelineModelItem'):
        ...

    @property
    @abstractmethod
    def children_nodes(self) -> List['PipelineModelItem']:
        ...

    def index_of(self, child: 'PipelineModelItem') -> int:
        return self.children_nodes.index(child)

    def child_node_at(self, row: int) -> 'PipelineModelItem' or None:
        if 0 <= row < len(self.children_nodes):
            return self.children_nodes[row]
        return None

    @property
    def row(self) -> int:
        if self.parent_node is not None:
            return self.parent_node.index_of(self)
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

    @abstractmethod
    def delete_node(self):
        ...


class QObjectPipelineModelItemMeta(type(QObject), ABCMeta):
    pass


class QObjectPipelineModelItem(PipelineModelItem):
    def __init__(self: QObject, name: str):
        super(QObjectPipelineModelItem, self).__init__()
        self.setObjectName(name)

    @property
    def name(self: QObject) -> str:
        return self.objectName()

    @name.setter
    def name(self: QObject, new_name: str):
        self.setObjectName(new_name)

    @property
    def parent_node(self: QObject) -> 'PipelineModelItem':
        return self.parent()

    @parent_node.setter
    @abstractmethod
    def parent_node(self: QObject, parent: 'PipelineModelItem'):
        self.setParent(parent)

    @property
    @abstractmethod
    def children_nodes(self: QObject) -> List['PipelineModelItem']:
        return self.children()

    def delete_node(self: QObject):
        log.debug(f"deleting node {type(self)}:{self.name}")
        self.deleteLater()


class QWidgetPipelineModelItemMeta(type(QWidget), ABCMeta):
    pass


class QWidgetPipelineModelItem(QObjectPipelineModelItem):
    def __init__(self: QWidget, name: str):
        super(QWidgetPipelineModelItem, self).__init__(name=name)

    @property
    def parent_node(self: QWidget) -> 'PipelineModelItem':
        return self.parentWidget()

    @parent_node.setter
    @abstractmethod
    def parent_node(self: QWidget, parent: QWidget):
        self.setParent(parent)

    @property
    @abstractmethod
    def children_nodes(self: QObject) -> List['PipelineModelItem']:
        return self.children()

    def delete_node(self: QObject):
        self.deleteLater()

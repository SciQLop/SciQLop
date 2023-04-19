from abc import ABC, abstractmethod, ABCMeta
from typing import List, Protocol, runtime_checkable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from ... import logging

log = logging.getLogger(__name__)


@runtime_checkable
class PipelineModelItem(Protocol):

    def __eq__(self, other: 'PipelineModelItem') -> bool:
        ...

    @property
    def icon(self) -> str:
        return ""

    @property
    def name(self) -> str:
        pass

    @name.setter
    def name(self, new_name: str):
        pass

    @property
    @abstractmethod
    def parent_node(self) -> 'PipelineModelItem':
        pass

    @parent_node.setter
    @abstractmethod
    def parent_node(self, parent: 'PipelineModelItem'):
        pass

    @property
    @abstractmethod
    def children_nodes(self) -> List['PipelineModelItem']:
        pass

    def remove_children_node(self, node: 'PipelineModelItem'):
        ...

    def add_children_node(self, node: 'PipelineModelItem'):
        ...

    def select(self):
        ...

    def unselect(self):
        ...

    def delete_node(self):
        ...


class MetaPipelineModelItem(type(QObject), type(PipelineModelItem)):
    pass
#
# class QObjectPipelineModelItemMeta(type(QObject), ABCMeta):
#     pass
#
#
# class QObjectPipelineModelItem(PipelineModelItem):
#     def __init__(self: QObject, name: str):
#         super(QObjectPipelineModelItem, self).__init__()
#         self.setObjectName(name)
#
#     @property
#     def name(self: QObject) -> str:
#         return self.objectName()
#
#     @name.setter
#     def name(self: QObject, new_name: str):
#         self.setObjectName(new_name)
#
#     @property
#     def parent_node(self: QObject) -> 'PipelineModelItem':
#         return self.parent()
#
#     @parent_node.setter
#     @abstractmethod
#     def parent_node(self: QObject, parent: 'PipelineModelItem'):
#         self.setParent(parent)
#
#     @property
#     @abstractmethod
#     def children_nodes(self: QObject) -> List['PipelineModelItem']:
#         return self.children()
#
#     def delete_node(self: QObject):
#         log.debug(f"deleting node {type(self)}:{self.name}")
#         self.deleteLater()
#
#
# class QWidgetPipelineModelItemMeta(type(QWidget), ABCMeta):
#     pass
#
#
# class QWidgetPipelineModelItem(QObjectPipelineModelItem):
#     def __init__(self: QWidget, name: str):
#         super(QWidgetPipelineModelItem, self).__init__(name=name)
#
#     @property
#     def parent_node(self: QWidget) -> 'PipelineModelItem':
#         return self.parentWidget()
#
#     @parent_node.setter
#     @abstractmethod
#     def parent_node(self: QWidget, parent: QWidget):
#         self.setParent(parent)
#
#     @property
#     @abstractmethod
#     def children_nodes(self: QObject) -> List['PipelineModelItem']:
#         return self.children()
#
#     def delete_node(self: QObject):
#         self.deleteLater()

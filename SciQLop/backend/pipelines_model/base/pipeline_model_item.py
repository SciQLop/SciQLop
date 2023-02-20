from typing import List


class PipelineModelItem:
    # __slots__ = ['_name', '_parent_item', '_children_items']

    def __init__(self, name: str, parent: 'PipelineModelItem' or None):
        self._name = name
        self._parent_item = parent

        if parent:
            parent.append_child(self)
        self._children_items: List['PipelineModelItem'] = []

    @property
    def icon(self):
        return ""

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, new_name: str):
        self._name = new_name

    @property
    def parent_item(self) -> 'PipelineModelItem':
        return self._parent_item

    @parent_item.setter
    def parent_item(self, parent: 'PipelineModelItem'):
        self._parent_item = parent

    @property
    def children_items(self) -> List['PipelineModelItem']:
        return self._children_items

    def append_child(self, child: 'PipelineModelItem'):
        child.parent_item = self
        self._children_items.append(child)

    def index_of(self, child: 'PipelineModelItem'):
        return self._children_items.index(child)

    def child_at(self, row: int) -> 'PipelineModelItem' or None:
        if 0 <= row < len(self._children_items):
            return self._children_items[row]
        return None

    @property
    def row(self) -> int:
        if self._parent_item is not None:
            return self._parent_item.index_of(self)
        return 0

    @property
    def child_count(self) -> int:
        return len(self._children_items)

    @property
    def column_count(self) -> int:
        return 1

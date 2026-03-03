from __future__ import annotations
from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, QSortFilterProxyModel
from PySide6.QtGui import Qt
from SciQLop.components.settings import SettingsCategory, ConfigEntry
from pydantic import BaseModel
from typing import Any


class SettingsNode:
    """A node in the settings tree. Lightweight, no Pydantic overhead."""

    __slots__ = ("name", "parent", "children", "entry_cls", "field_name", "field_info")

    def __init__(self, name: str, parent: SettingsNode | None = None,
                 entry_cls: type[ConfigEntry] | None = None,
                 field_name: str | None = None, field_info: Any = None):
        self.name = name
        self.parent = parent
        self.children: list[SettingsNode] = []
        self.entry_cls = entry_cls
        self.field_name = field_name
        self.field_info = field_info

    def row(self) -> int:
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0

    def append(self, child: SettingsNode) -> SettingsNode:
        child.parent = self
        self.children.append(child)
        return child


def _build_entry_node(entry_cls: type[ConfigEntry], parent: SettingsNode) -> SettingsNode:
    """Recursively build nodes for a ConfigEntry and its fields."""
    node = SettingsNode(name=entry_cls.__name__, parent=parent, entry_cls=entry_cls)
    for field_name, field_info in entry_cls.model_fields.items():
        annotation = field_info.annotation
        # If the field is itself a ConfigEntry subclass, recurse
        if isinstance(annotation, type) and issubclass(annotation, ConfigEntry):
            child = _build_entry_node(annotation, node)
            child.field_name = field_name
            child.field_info = field_info
            node.children.append(child)
        else:
            node.children.append(
                SettingsNode(name=field_name, parent=node,
                             field_name=field_name, field_info=field_info)
            )
    return node


def build_settings_tree() -> SettingsNode:
    """Build the full settings tree: root → categories → subcategories → entries → fields."""
    root = SettingsNode(name="root")

    # Group entries by category, then subcategory
    cat_map: dict[str, dict[str, list[type[ConfigEntry]]]] = {}
    for cls in ConfigEntry.list_entries().values():
        cat_map.setdefault(cls.category, {}).setdefault(cls.subcategory, []).append(cls)

    for category, subcats in sorted(cat_map.items()):
        cat_node = root.append(SettingsNode(name=category))
        for subcategory, entry_classes in sorted(subcats.items()):
            subcat_node = cat_node.append(SettingsNode(name=subcategory))
            for entry_cls in entry_classes:
                entry_node = _build_entry_node(entry_cls, subcat_node)
                subcat_node.children.append(entry_node)

    return root


class SettingsModel(QAbstractItemModel):
    """Tree model: root → category → subcategory → entry → field (recursive)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = SettingsNode(name="root")

    def rebuild(self):
        """Rebuild the tree from current ConfigEntry registry."""
        self.beginResetModel()
        self._root = build_settings_tree()
        self.endResetModel()

    def root(self) -> SettingsNode:
        return self._root

    def node_from_index(self, index: QModelIndex) -> SettingsNode:
        if not index.isValid():
            return self._root
        return index.internalPointer()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        node = self.node_from_index(parent)
        return len(node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        parent_node = self.node_from_index(parent)
        if row < 0 or row >= len(parent_node.children):
            return QModelIndex()
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node: SettingsNode = index.internalPointer()
        if node.parent is None or node.parent is self._root:
            return QModelIndex()
        return self.createIndex(node.parent.row(), 0, node.parent)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return index.internalPointer().name
        return None


class SettingsFilterProxyModel(QSortFilterProxyModel):
    """Proxy that filters the category list. A category is shown if its name
    or any descendant node name matches the filter string."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_model = SettingsModel(self)
        self.setSourceModel(self._source_model)

    def rebuild(self):
        """Rebuild the underlying source model from current entries."""
        self._source_model.rebuild()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True
        index = self.sourceModel().index(source_row, 0, source_parent)
        return self._matches_recursive(index)

    def _matches_recursive(self, index: QModelIndex) -> bool:
        node: SettingsNode = index.internalPointer()
        if self.filterRegularExpression().match(node.name).hasMatch():
            return True
        for i in range(self.sourceModel().rowCount(index)):
            child_index = self.sourceModel().index(i, 0, index)
            if self._matches_recursive(child_index):
                return True
        return False

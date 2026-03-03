from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from ..backend.provider import Catalog, CatalogProvider
from ..backend.registry import CatalogRegistry


class _Node:
    """Internal tree node: root -> provider -> catalog."""

    __slots__ = ("name", "parent", "children", "provider", "catalog")

    def __init__(
        self,
        name: str,
        parent: _Node | None = None,
        provider: CatalogProvider | None = None,
        catalog: Catalog | None = None,
    ):
        self.name = name
        self.parent = parent
        self.children: list[_Node] = []
        self.provider = provider
        self.catalog = catalog

    def row(self) -> int:
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0


class CatalogTreeModel(QAbstractItemModel):
    """Qt item model: root -> provider -> catalog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = _Node(name="root")
        self._registry = CatalogRegistry.instance()

        # Populate with existing providers (skip dead ones)
        for provider in self._registry.providers():
            try:
                self._add_provider_node(provider)
            except (RuntimeError, AttributeError):
                pass  # provider may have been partially destroyed

        # Listen for future changes
        self._registry.provider_registered.connect(self._on_provider_registered)
        self._registry.provider_unregistered.connect(self._on_provider_unregistered)

    # ---- internal helpers ----

    def _find_or_create_folder(self, parent: _Node, name: str, provider: CatalogProvider) -> _Node:
        """Find existing folder child or create a new one."""
        for child in parent.children:
            if child.catalog is None and child.name == name:
                return child
        folder = _Node(name=name, parent=parent, provider=provider)
        parent.children.append(folder)
        return folder

    def _add_provider_node(self, provider: CatalogProvider) -> _Node:
        node = _Node(name=provider.name, parent=self._root, provider=provider)
        for cat in provider.catalogs():
            target = node
            for segment in cat.path:
                target = self._find_or_create_folder(target, segment, provider)
            child = _Node(name=cat.name, parent=target, provider=provider, catalog=cat)
            target.children.append(child)
        self._root.children.append(node)

        # Connect to provider signals for dynamic updates
        provider.catalog_added.connect(lambda cat, p=provider, n=node: self._on_catalog_added(p, n, cat))
        provider.catalog_removed.connect(lambda cat, p=provider, n=node: self._on_catalog_removed(p, n, cat))
        return node

    def _provider_node(self, provider: CatalogProvider) -> _Node | None:
        for child in self._root.children:
            if child.provider is provider:
                return child
        return None

    # ---- slots ----

    def _on_provider_registered(self, provider: object) -> None:
        # Guard: provider.catalogs() may fail if __init__ hasn't finished
        try:
            _ = provider.catalogs()
        except (RuntimeError, AttributeError):
            return
        row = len(self._root.children)
        self.beginInsertRows(QModelIndex(), row, row)
        self._add_provider_node(provider)
        self.endInsertRows()

    def _on_provider_unregistered(self, provider: object) -> None:
        node = self._provider_node(provider)
        if node is None:
            return
        row = node.row()
        self.beginRemoveRows(QModelIndex(), row, row)
        self._root.children.remove(node)
        self.endRemoveRows()

    def _on_catalog_added(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
        parent_index = self.createIndex(pnode.row(), 0, pnode)
        row = len(pnode.children)
        self.beginInsertRows(parent_index, row, row)
        child = _Node(name=catalog.name, parent=pnode, provider=provider, catalog=catalog)
        pnode.children.append(child)
        self.endInsertRows()

    def _on_catalog_removed(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
        for i, child in enumerate(pnode.children):
            if child.catalog is catalog:
                parent_index = self.createIndex(pnode.row(), 0, pnode)
                self.beginRemoveRows(parent_index, i, i)
                pnode.children.pop(i)
                self.endRemoveRows()
                return

    # ---- QAbstractItemModel interface ----

    def node_from_index(self, index: QModelIndex) -> _Node:
        if not index.isValid():
            return self._root
        return index.internalPointer()

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = self.node_from_index(parent)
        child = parent_node.children[row]
        return self.createIndex(row, column, child)

    def parent(self, index: QModelIndex = None) -> QModelIndex:
        if index is None or not index.isValid():
            return QModelIndex()
        child_node = index.internalPointer()
        parent_node = child_node.parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        return self.createIndex(parent_node.row(), 0, parent_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        node = self.node_from_index(parent)
        return len(node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            node = index.internalPointer()
            return node.name
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

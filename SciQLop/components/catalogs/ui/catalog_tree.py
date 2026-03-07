from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from ..backend.provider import Catalog, CatalogProvider
from ..backend.registry import CatalogRegistry

DIRTY_PROVIDER_ROLE = Qt.ItemDataRole.UserRole + 1


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
        self._provider_connections: dict[int, list[tuple]] = {}
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
        on_added = lambda cat, p=provider, n=node: self._on_catalog_added(p, n, cat)
        on_removed = lambda cat, p=provider, n=node: self._on_catalog_removed(p, n, cat)
        on_dirty = lambda cat, dirty, p=provider, n=node: self._on_dirty_changed(p, n, cat, dirty)
        provider.catalog_added.connect(on_added)
        provider.catalog_removed.connect(on_removed)
        provider.dirty_changed.connect(on_dirty)
        self._provider_connections[id(provider)] = [
            (provider.catalog_added, on_added),
            (provider.catalog_removed, on_removed),
            (provider.dirty_changed, on_dirty),
        ]
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
        # Disconnect provider signals before removing the node
        for signal, slot in self._provider_connections.pop(id(provider), []):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        node = self._provider_node(provider)
        if node is None:
            return
        row = node.row()
        self.beginRemoveRows(QModelIndex(), row, row)
        self._root.children.remove(node)
        self.endRemoveRows()

    def _on_dirty_changed(self, provider: CatalogProvider, pnode: _Node, catalog: object, is_dirty: bool) -> None:
        cat_node = self._find_catalog_node(pnode, catalog)
        if cat_node is not None:
            idx = self.createIndex(cat_node.row(), 0, cat_node)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])
        pnode_idx = self.createIndex(pnode.row(), 0, pnode)
        self.dataChanged.emit(pnode_idx, pnode_idx, [Qt.ItemDataRole.DisplayRole, DIRTY_PROVIDER_ROLE])

    def _find_catalog_node(self, node: _Node, catalog: object) -> _Node | None:
        for child in node.children:
            if child.catalog is not None and child.catalog.uuid == catalog.uuid:
                return child
            found = self._find_catalog_node(child, catalog)
            if found is not None:
                return found
        return None

    def _on_catalog_added(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
        target = pnode
        target_index = self.createIndex(pnode.row(), 0, pnode)
        for segment in catalog.path:
            existing = None
            for child in target.children:
                if child.catalog is None and child.name == segment:
                    existing = child
                    break
            if existing is not None:
                target = existing
                target_index = self.createIndex(existing.row(), 0, existing)
            else:
                row = len(target.children)
                self.beginInsertRows(target_index, row, row)
                folder = _Node(name=segment, parent=target, provider=provider)
                target.children.append(folder)
                self.endInsertRows()
                target = folder
                target_index = self.createIndex(folder.row(), 0, folder)

        row = len(target.children)
        self.beginInsertRows(target_index, row, row)
        child = _Node(name=catalog.name, parent=target, provider=provider, catalog=catalog)
        target.children.append(child)
        self.endInsertRows()

    def _on_catalog_removed(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
        self._remove_catalog_recursive(pnode, catalog)

    def _remove_catalog_recursive(self, node: _Node, catalog: object) -> bool:
        """Find and remove catalog node, then prune empty folders. Returns True if found."""
        for i, child in enumerate(node.children):
            if child.catalog is catalog:
                parent_index = self.createIndex(node.row(), 0, node) if node.parent is not None else QModelIndex()
                self.beginRemoveRows(parent_index, i, i)
                node.children.pop(i)
                self.endRemoveRows()
                # Prune empty folder ancestors
                self._prune_if_empty(node)
                return True
            if child.catalog is None and self._remove_catalog_recursive(child, catalog):
                return True
        return False

    def _prune_if_empty(self, node: _Node) -> None:
        """Remove node if it's an empty folder (not provider, not root)."""
        if node.parent is None:
            return
        if node.catalog is not None:
            return  # not a folder
        if node.parent.parent is None:
            return  # node is a provider node, don't prune
        if len(node.children) > 0:
            return  # not empty
        parent = node.parent
        i = parent.children.index(node)
        parent_index = self.createIndex(parent.row(), 0, parent) if parent.parent is not None else QModelIndex()
        self.beginRemoveRows(parent_index, i, i)
        parent.children.pop(i)
        self.endRemoveRows()
        self._prune_if_empty(parent)

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
            name = node.name
            if node.provider is not None:
                if node.catalog is not None:
                    if node.provider.is_dirty(node.catalog):
                        name += " *"
                elif node.parent is self._root:
                    if node.provider.is_dirty():
                        name += " *"
            return name
        if role == DIRTY_PROVIDER_ROLE:
            node = index.internalPointer()
            if node.provider is not None and node.parent is self._root:
                from ..backend.provider import Capability
                has_save = Capability.SAVE in node.provider.capabilities()
                return has_save and node.provider.is_dirty()
            return False
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

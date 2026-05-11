from __future__ import annotations

from enum import Enum
from typing import Any, TYPE_CHECKING

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from ..backend.provider import Catalog, CatalogProvider
from ..backend.registry import CatalogRegistry

if TYPE_CHECKING:
    from ..backend.provider import NodeType

DIRTY_PROVIDER_ROLE = Qt.ItemDataRole.UserRole + 1
LOADING_ROLE = Qt.ItemDataRole.UserRole + 2


class _PlaceholderType(str, Enum):
    NONE = "none"
    CATALOG = "catalog"
    FOLDER = "folder"


class _Node:
    """Internal tree node: root -> provider -> folder -> catalog."""

    __slots__ = ("name", "parent", "children", "provider", "catalog",
                 "placeholder_type", "is_explicit_folder")

    def __init__(
        self,
        name: str,
        parent: _Node | None = None,
        provider: CatalogProvider | None = None,
        catalog: Catalog | None = None,
        placeholder_type: _PlaceholderType = _PlaceholderType.NONE,
        is_explicit_folder: bool = False,
    ):
        self.name = name
        self.parent = parent
        self.children: list[_Node] = []
        self.provider = provider
        self.catalog = catalog
        self.placeholder_type = placeholder_type
        self.is_explicit_folder = is_explicit_folder

    @property
    def is_placeholder(self) -> bool:
        return self.placeholder_type != _PlaceholderType.NONE

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
        self._loading_uuids: set[str] = set()
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
            if child.catalog is None and child.name == name and not child.is_placeholder:
                return child
        folder = _Node(name=name, parent=parent, provider=provider)
        parent.children.append(folder)
        return folder

    @staticmethod
    def _insert_pos_before_placeholders(node: _Node) -> int:
        """Return the index of the first placeholder child, or len(children) if none."""
        for i, child in enumerate(node.children):
            if child.is_placeholder:
                return i
        return len(node.children)

    def _ensure_placeholders(self, node: _Node, node_index: QModelIndex) -> None:
        """Add catalog and folder placeholder children if not already present and provider supports creation."""
        if node.provider is None or not self._supports_create(node.provider):
            return
        has_cat_ph = any(c.placeholder_type == _PlaceholderType.CATALOG for c in node.children)
        has_folder_ph = any(c.placeholder_type == _PlaceholderType.FOLDER for c in node.children)
        to_add = []
        if not has_cat_ph:
            to_add.append(_Node(name="New Catalog...", parent=node, provider=node.provider,
                                placeholder_type=_PlaceholderType.CATALOG))
        if not has_folder_ph:
            to_add.append(_Node(name="New Folder...", parent=node, provider=node.provider,
                                placeholder_type=_PlaceholderType.FOLDER))
        if to_add:
            start = len(node.children)
            self.beginInsertRows(node_index, start, start + len(to_add) - 1)
            node.children.extend(to_add)
            self.endInsertRows()

    def _supports_create(self, provider: CatalogProvider) -> bool:
        from ..backend.provider import Capability
        return Capability.CREATE_CATALOGS in provider.capabilities()

    def _add_placeholders_recursive(self, node: _Node, provider: CatalogProvider) -> None:
        """Add placeholder pairs to node and all folder descendants (initial population only)."""
        for child in node.children:
            if child.catalog is None and not child.is_placeholder:
                self._add_placeholders_recursive(child, provider)
        node.children.append(_Node(name="New Catalog...", parent=node, provider=provider,
                                    placeholder_type=_PlaceholderType.CATALOG))
        node.children.append(_Node(name="New Folder...", parent=node, provider=provider,
                                    placeholder_type=_PlaceholderType.FOLDER))

    def _add_provider_node(self, provider: CatalogProvider) -> _Node:
        node = _Node(name=provider.name, parent=self._root, provider=provider)
        for cat in provider.catalogs():
            target = node
            for segment in cat.path:
                target = self._find_or_create_folder(target, segment, provider)
            child = _Node(name=cat.name, parent=target, provider=provider, catalog=cat)
            target.children.append(child)
        if self._supports_create(provider):
            self._add_placeholders_recursive(node, provider)
        self._root.children.append(node)

        # Connect to provider signals for dynamic updates
        on_added = lambda cat, p=provider, n=node: self._on_catalog_added(p, n, cat)
        on_removed = lambda cat, p=provider, n=node: self._on_catalog_removed(p, n, cat)
        on_dirty = lambda cat, dirty, p=provider, n=node: self._on_dirty_changed(p, n, cat, dirty)
        on_renamed = lambda cat, p=provider, n=node: self._on_catalog_renamed(p, n, cat)
        on_moved = lambda cat, p=provider, n=node: self._on_catalog_moved(p, n, cat)
        on_folder_added = lambda path, p=provider, n=node: self._on_folder_added(p, n, path)
        on_folder_removed = lambda path, p=provider, n=node: self._on_folder_removed(p, n, path)
        on_status = lambda p=provider, n=node: self._on_provider_status_changed(n)
        on_load_start = lambda cat, p=provider, n=node: self._on_loading_changed(p, n, cat, True)
        on_load_end = lambda cat, p=provider, n=node: self._on_loading_changed(p, n, cat, False)
        provider.catalog_added.connect(on_added)
        provider.catalog_removed.connect(on_removed)
        provider.dirty_changed.connect(on_dirty)
        provider.catalog_renamed.connect(on_renamed)
        provider.catalog_moved.connect(on_moved)
        provider.folder_added.connect(on_folder_added)
        provider.folder_removed.connect(on_folder_removed)
        provider.status_changed.connect(on_status)
        provider.loading_started.connect(on_load_start)
        provider.loading_finished.connect(on_load_end)
        self._provider_connections[id(provider)] = [
            (provider.catalog_added, on_added),
            (provider.catalog_removed, on_removed),
            (provider.dirty_changed, on_dirty),
            (provider.catalog_renamed, on_renamed),
            (provider.catalog_moved, on_moved),
            (provider.folder_added, on_folder_added),
            (provider.folder_removed, on_folder_removed),
            (provider.status_changed, on_status),
            (provider.loading_started, on_load_start),
            (provider.loading_finished, on_load_end),
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
        if catalog is not None:
            cat_node = self._find_catalog_node(pnode, catalog)
            if cat_node is not None:
                idx = self.createIndex(cat_node.row(), 0, cat_node)
                self.dataChanged.emit(idx, idx, [int(Qt.ItemDataRole.DisplayRole)])
        pnode_idx = self.createIndex(pnode.row(), 0, pnode)
        self.dataChanged.emit(pnode_idx, pnode_idx, [int(Qt.ItemDataRole.DisplayRole), DIRTY_PROVIDER_ROLE])

    def _find_catalog_node(self, node: _Node, catalog: object) -> _Node | None:
        for child in node.children:
            if child.catalog is not None and child.catalog.uuid == catalog.uuid:
                return child
            found = self._find_catalog_node(child, catalog)
            if found is not None:
                return found
        return None

    def _on_catalog_renamed(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
        cat_node = self._find_catalog_node(pnode, catalog)
        if cat_node is not None:
            cat_node.name = catalog.name
            idx = self.createIndex(cat_node.row(), 0, cat_node)
            self.dataChanged.emit(idx, idx, [int(Qt.ItemDataRole.DisplayRole)])

    def _on_catalog_moved(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
        """Relocate the catalog node to its new path. The catalog object's
        path has already been updated by the provider."""
        if self._find_catalog_node(pnode, catalog) is None:
            return
        self._remove_catalog_recursive(pnode, catalog)
        self._on_catalog_added(provider, pnode, catalog)

    def _on_catalog_added(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
        if self._find_catalog_node(pnode, catalog) is not None:
            return  # already in tree, avoid duplicate
        target = pnode
        target_index = self.createIndex(pnode.row(), 0, pnode)
        for segment in catalog.path:
            existing = None
            for child in target.children:
                if child.catalog is None and child.name == segment and not child.is_placeholder:
                    existing = child
                    break
            if existing is not None:
                target = existing
                target_index = self.createIndex(existing.row(), 0, existing)
            else:
                row = self._insert_pos_before_placeholders(target)
                self.beginInsertRows(target_index, row, row)
                folder = _Node(name=segment, parent=target, provider=provider)
                target.children.insert(row, folder)
                self.endInsertRows()
                target = folder
                target_index = self.createIndex(folder.row(), 0, folder)
                self._ensure_placeholders(folder, target_index)

        row = self._insert_pos_before_placeholders(target)
        self.beginInsertRows(target_index, row, row)
        child = _Node(name=catalog.name, parent=target, provider=provider, catalog=catalog)
        target.children.insert(row, child)
        self.endInsertRows()

    def _on_catalog_removed(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
        self._remove_catalog_recursive(pnode, catalog)

    def _on_folder_added(self, provider: CatalogProvider, pnode: _Node, path: list) -> None:
        target = pnode
        target_index = self.createIndex(pnode.row(), 0, pnode)
        for segment in path:
            existing = None
            for child in target.children:
                if child.catalog is None and child.name == segment and not child.is_placeholder:
                    existing = child
                    break
            if existing is not None:
                existing.is_explicit_folder = True
                target = existing
                target_index = self.createIndex(existing.row(), 0, existing)
            else:
                row = self._insert_pos_before_placeholders(target)
                self.beginInsertRows(target_index, row, row)
                folder = _Node(name=segment, parent=target, provider=provider, is_explicit_folder=True)
                target.children.insert(row, folder)
                self.endInsertRows()
                target = folder
                target_index = self.createIndex(folder.row(), 0, folder)
        self._ensure_placeholders(target, target_index)

    def _on_folder_removed(self, provider: CatalogProvider, pnode: _Node, path: list) -> None:
        target = pnode
        for segment in path:
            found = None
            for child in target.children:
                if child.catalog is None and child.name == segment:
                    found = child
                    break
            if found is None:
                return
            target = found
        parent = target.parent
        if parent is None:
            return
        i = parent.children.index(target)
        parent_index = self.createIndex(parent.row(), 0, parent) if parent.parent is not None else QModelIndex()
        self.beginRemoveRows(parent_index, i, i)
        parent.children.pop(i)
        self.endRemoveRows()

    def _on_loading_changed(self, provider: CatalogProvider, pnode: _Node, catalog: object, loading: bool) -> None:
        if loading:
            self._loading_uuids.add(catalog.uuid)
        else:
            self._loading_uuids.discard(catalog.uuid)
        cat_node = self._find_catalog_node(pnode, catalog)
        if cat_node is not None:
            idx = self.createIndex(cat_node.row(), 0, cat_node)
            self.dataChanged.emit(idx, idx, [LOADING_ROLE])

    def _on_provider_status_changed(self, pnode: _Node) -> None:
        idx = self.createIndex(pnode.row(), 0, pnode)
        self.dataChanged.emit(idx, idx, [int(Qt.ItemDataRole.DisplayRole), int(Qt.ItemDataRole.DecorationRole)])

    def _remove_catalog_recursive(self, node: _Node, catalog: object) -> bool:
        """Find and remove catalog node, then prune empty folders. Returns True if found."""
        for i, child in enumerate(node.children):
            if child.catalog is not None and child.catalog.uuid == catalog.uuid:
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
        """Remove node if it's an empty folder (not provider, not root, not explicit)."""
        if node.parent is None:
            return
        if node.catalog is not None:
            return  # not a folder
        if node.parent.parent is None:
            return  # node is a provider node, don't prune
        if node.is_explicit_folder:
            return  # explicit folders persist even when empty
        if any(not c.is_placeholder for c in node.children):
            return  # has real children
        # Remove placeholder children first
        node_index = self.createIndex(node.row(), 0, node)
        if node.children:
            self.beginRemoveRows(node_index, 0, len(node.children) - 1)
            node.children.clear()
            self.endRemoveRows()
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

    def _folder_path(self, node: _Node) -> list[str]:
        """Build the path from provider node down to this folder node."""
        segments = []
        n = node
        while n.parent is not None and n.parent.parent is not None:
            segments.append(n.name)
            n = n.parent
        segments.reverse()
        return segments

    def _node_type(self, node: _Node) -> "NodeType":
        from ..backend.provider import NodeType
        if node.catalog is not None:
            return NodeType.CATALOG
        if node.parent is self._root:
            return NodeType.PROVIDER
        return NodeType.FOLDER

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            node = index.internalPointer()
            if node.is_explicit_folder and node.provider is not None:
                custom = node.provider.folder_display_name(self._folder_path(node))
                if custom is not None:
                    return custom
            name = node.name
            if node.provider is not None:
                from ..backend.provider import Capability
                has_save = Capability.SAVE in node.provider.capabilities()
                if has_save:
                    if node.catalog is not None:
                        if node.provider.is_dirty(node.catalog):
                            name += " *"
                    elif node.parent is self._root:
                        if node.provider.is_dirty():
                            name += " *"
            return name
        if role == Qt.ItemDataRole.FontRole:
            node = index.internalPointer()
            if node.is_placeholder:
                from PySide6.QtGui import QFont
                font = QFont()
                font.setItalic(True)
                return font
            return None
        if role == Qt.ItemDataRole.ForegroundRole:
            node = index.internalPointer()
            if node.is_placeholder:
                from PySide6.QtGui import QColor
                return QColor(128, 128, 128)
            return None
        if role == Qt.ItemDataRole.DecorationRole:
            node = index.internalPointer()
            if node.is_placeholder:
                return None
            from ..backend.provider import NodeType
            from ...theming.icons import get_icon
            node_type = self._node_type(node)
            if node.provider is not None:
                custom = node.provider.node_icon(node_type, self._folder_path(node) if node_type == NodeType.FOLDER else None)
                if custom is not None:
                    return custom
            icon_map = {
                NodeType.PROVIDER: "dataSourceRoot",
                NodeType.FOLDER: "folder_open",
                NodeType.CATALOG: "catalogue",
            }
            icon_name = icon_map.get(node_type)
            return get_icon(icon_name) if icon_name else None
        if role == DIRTY_PROVIDER_ROLE:
            node = index.internalPointer()
            if node.provider is not None and node.parent is self._root:
                from ..backend.provider import Capability
                has_save = Capability.SAVE in node.provider.capabilities()
                return has_save and node.provider.is_dirty()
            return False
        if role == LOADING_ROLE:
            node = index.internalPointer()
            if node.catalog is not None:
                return node.catalog.uuid in self._loading_uuids
            return False
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        node = index.internalPointer()
        name = value.strip() if isinstance(value, str) else str(value).strip()
        if not name:
            return False
        if node.placeholder_type == _PlaceholderType.CATALOG:
            path = self._folder_path(node.parent)
            node.provider.create_catalog(name, path=path if path else None)
            return True
        if node.placeholder_type == _PlaceholderType.FOLDER:
            parent = node.parent
            parent_index = self.createIndex(parent.row(), 0, parent) if parent.parent is not None else QModelIndex()
            insert_row = next(
                (i for i, c in enumerate(parent.children) if c.is_placeholder),
                len(parent.children)
            )
            folder = _Node(name=name, parent=parent, provider=node.provider)
            self.beginInsertRows(parent_index, insert_row, insert_row)
            parent.children.insert(insert_row, folder)
            self.endInsertRows()
            folder_index = self.createIndex(insert_row, 0, folder)
            self._ensure_placeholders(folder, folder_index)
            return True
        if node.catalog is not None and node.provider is not None:
            from ..backend.provider import Capability
            if Capability.RENAME_CATALOG in node.provider.capabilities():
                node.provider.rename_catalog(node.catalog, name)
                node.name = name
                self.dataChanged.emit(index, index, [int(Qt.ItemDataRole.DisplayRole)])
                return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        node = index.internalPointer()
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if node.is_placeholder:
            return base | Qt.ItemFlag.ItemIsEditable
        from ..backend.provider import Capability
        if node.catalog is not None:
            base |= Qt.ItemFlag.ItemIsDragEnabled
            if (node.provider is not None
                    and Capability.RENAME_CATALOG in node.provider.capabilities()):
                base |= Qt.ItemFlag.ItemIsEditable
        if node.provider is not None and self._node_accepts_drop(node):
            base |= Qt.ItemFlag.ItemIsDropEnabled
        return base

    def _node_accepts_drop(self, node: _Node) -> bool:
        """A node accepts drops if its provider can either accept a moved
        catalog (same-provider drop) or create a new catalog there
        (cross-provider drop)."""
        from ..backend.provider import Capability
        caps = node.provider.capabilities()
        return Capability.CREATE_CATALOGS in caps or Capability.MOVE_CATALOG in caps

    def mimeTypes(self) -> list[str]:
        from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE
        return [CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE]

    def mimeData(self, indexes):
        from SciQLop.core.mime import encode_mime
        catalogs: list = []
        seen: set[str] = set()
        for idx in indexes:
            if not idx.isValid():
                continue
            node = idx.internalPointer()
            if node.catalog is not None and node.catalog.uuid not in seen:
                catalogs.append(node.catalog)
                seen.add(node.catalog.uuid)
        if not catalogs:
            return None
        return encode_mime(catalogs)

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def supportedDragActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def _resolve_drop_target(self, parent: QModelIndex):
        """Walk up to a folder/provider node, returning (provider_node,
        sub_path) or None if no valid drop target."""
        if not parent.isValid():
            return None
        node = parent.internalPointer()
        if node.is_placeholder:
            return None
        # Drop on a catalog → treat as drop on its parent folder
        if node.catalog is not None:
            node = node.parent
        if node is None or node.provider is None:
            return None
        provider_node = node
        while provider_node.parent is not None and provider_node.parent is not self._root:
            provider_node = provider_node.parent
        sub_path = self._folder_path(node) if node is not provider_node else []
        return provider_node, sub_path

    def canDropMimeData(self, data, action, row, column, parent) -> bool:
        from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE
        from ..backend.provider import Capability
        if data.hasFormat(EVENT_LIST_MIME_TYPE):
            if not parent.isValid():
                return False
            node = parent.internalPointer()
            if node.catalog is None or node.provider is None:
                return False
            caps = node.provider.capabilities()
            return Capability.CREATE_EVENTS in caps or Capability.EDIT_EVENTS in caps
        if not data.hasFormat(CATALOG_LIST_MIME_TYPE):
            return False
        target = self._resolve_drop_target(parent)
        if target is None:
            return False
        provider_node, _ = target
        caps = provider_node.provider.capabilities()
        return Capability.CREATE_CATALOGS in caps or Capability.MOVE_CATALOG in caps

    def dropMimeData(self, data, action, row, column, parent) -> bool:
        from SciQLop.core.mime import decode_mime
        from ..backend.provider import Capability, CatalogEvent
        from SciQLop.components.sciqlop_logging import getLogger
        import uuid as _uuid
        log = getLogger(__name__)
        if action == Qt.DropAction.IgnoreAction:
            return True

        from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE
        if data.hasFormat(EVENT_LIST_MIME_TYPE):
            return self._drop_events(data, parent, log)

        catalogs = decode_mime(data)
        if not catalogs:
            return False
        target = self._resolve_drop_target(parent)
        if target is None:
            return False
        dest_provider_node, dest_sub_path = target
        dest_provider = dest_provider_node.provider
        dest_caps = dest_provider.capabilities()
        for source_cat in catalogs:
            try:
                if source_cat.provider is dest_provider:
                    if Capability.MOVE_CATALOG not in dest_caps:
                        continue
                    if list(source_cat.path) == list(dest_sub_path):
                        continue
                    dest_provider.move_catalog(source_cat, dest_sub_path)
                else:
                    if Capability.CREATE_CATALOGS not in dest_caps:
                        continue
                    new_name = self._unique_catalog_name(
                        dest_provider, dest_sub_path, source_cat.name,
                    )
                    new_cat = dest_provider.create_catalog(new_name, path=dest_sub_path)
                    source_events = source_cat.provider.events(source_cat) if source_cat.provider else []
                    for ev in source_events:
                        copied = CatalogEvent(
                            uuid=str(_uuid.uuid4()),
                            start=ev.start, stop=ev.stop,
                            meta=dict(ev.meta),
                        )
                        dest_provider.add_event(new_cat, copied)
            except Exception as e:
                log.warning("Catalog drop failed for %r → %r: %s",
                            source_cat.name, dest_sub_path, e)
        # Return False so Qt does not also call removeRows() on the source —
        # provider signals (move/remove/add) drive tree updates instead.
        return False

    def _drop_events(self, data, parent, log) -> bool:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from ..backend.event_mime import decode_event_list
        from ..backend.registry import CatalogRegistry

        payload = decode_event_list(data)
        if payload is None or not parent.isValid():
            return False
        target_node = parent.internalPointer()
        target_catalog = target_node.catalog
        if target_catalog is None or target_node.provider is None:
            return False

        registry = CatalogRegistry.instance()
        source_provider = registry.provider_by_name(payload.provider)
        source_catalog = None
        source_events = []
        if source_provider is not None and payload.catalog_uuid is not None:
            for c in source_provider.catalogs():
                if c.uuid == payload.catalog_uuid:
                    source_catalog = c
                    break
            if source_catalog is not None:
                by_uuid = {e.uuid: e for e in source_provider.events(source_catalog)}
                source_events = [by_uuid[u] for u in payload.event_uuids if u in by_uuid]
        if not source_events:
            return False

        mods = QApplication.keyboardModifiers()
        cross_provider = source_provider is not target_node.provider
        if cross_provider:
            drop_action = "duplicate"
        elif mods & Qt.KeyboardModifier.ShiftModifier:
            drop_action = "move"
        elif mods & Qt.KeyboardModifier.ControlModifier:
            drop_action = "duplicate"
        else:
            drop_action = "link"

        try:
            target_node.provider.handle_event_drop(
                target_catalog=target_catalog,
                events=source_events,
                action=drop_action,
                source_catalog=source_catalog,
            )
        except Exception as e:
            log.warning("Event drop failed: %s", e)
        return False

    def _unique_catalog_name(self, provider, sub_path: list[str], base: str) -> str:
        existing = {
            c.name for c in provider.catalogs()
            if list(c.path) == list(sub_path)
        }
        if base not in existing:
            return base
        for i in range(2, 1000):
            candidate = f"{base} ({i})"
            if candidate not in existing:
                return candidate
        return f"{base} ({_uuid_short()})"


def _uuid_short() -> str:
    import uuid as _uuid
    return str(_uuid.uuid4())[:8]

"""The catalogue tree: sections (My catalogues, Shared, Reference), then what each provider places
in them.

A provider places either all its catalogues as one group, or each of its top-level folders as a
group (cocat-rs: one group per project). A group shows as a node in its section, or inline: its
content directly in the section (the person's own project in My catalogues). Every node keeps its
provider and its path in that provider, so nothing is derived from a node's depth.
"""
from __future__ import annotations

from enum import Enum
from html import escape
from typing import Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal

from ..backend.color_palette import catalog_color_changed
from ..backend.provider import Capability, Catalog, CatalogProvider, NodeType, Placement, Section
from ..backend.registry import CatalogRegistry

DIRTY_PROVIDER_ROLE = Qt.ItemDataRole.UserRole + 1
LOADING_ROLE = Qt.ItemDataRole.UserRole + 2

SECTION_ORDER = (Section.MINE, Section.SHARED, Section.REFERENCE)
SECTION_LABELS = {Section.MINE: "My catalogues", Section.SHARED: "Shared", Section.REFERENCE: "Reference"}
SECTION_ICONS = {Section.MINE: "home", Section.SHARED: "collab", Section.REFERENCE: "catalogue"}
SECTION_TIPS = {
    Section.MINE: "Your own catalogues. New catalogues go here.",
    Section.SHARED: "Projects shared with other people, yours or theirs.",
    Section.REFERENCE: "Read-only lists from outside: public catalogues, AMDA, plugins.",
}
FALLBACK = Placement(Section.REFERENCE)  # a provider that places its folders: its root-level catalogues


class _PlaceholderType(str, Enum):
    NONE = "none"
    CATALOG = "catalog"
    FOLDER = "folder"


class _Kind(str, Enum):
    ROOT = "root"
    SECTION = "section"
    GROUP = "group"      # a provider, or one of its top folders, shown as a node
    FOLDER = "folder"
    CATALOG = "catalog"
    PLACEHOLDER = "placeholder"
    NOTE = "note"        # a line of text from a provider (e.g. "Sign in to see shared projects")


class _Node:
    __slots__ = ("name", "parent", "children", "kind", "provider", "path", "catalog",
                 "placeholder_type", "is_explicit_folder", "section", "group")

    def __init__(self, name: str, parent: _Node | None = None, kind: _Kind = _Kind.FOLDER,
                 provider: CatalogProvider | None = None, path: list[str] | None = None,
                 catalog: Catalog | None = None,
                 placeholder_type: _PlaceholderType = _PlaceholderType.NONE,
                 is_explicit_folder: bool = False, section: Section | None = None,
                 group: str | None = None):
        self.name = name
        self.parent = parent
        self.children: list[_Node] = []
        self.kind = kind
        self.provider = provider
        self.path = list(path or [])
        self.catalog = catalog
        self.placeholder_type = placeholder_type
        self.is_explicit_folder = is_explicit_folder
        self.section = section
        self.group = group  # GROUP nodes: the top folder they stand for, None for a whole provider

    @property
    def is_placeholder(self) -> bool:
        return self.placeholder_type != _PlaceholderType.NONE

    @property
    def is_provider_node(self) -> bool:
        """The node of a provider placed as a whole: where its provider-level actions are."""
        return self.kind == _Kind.GROUP and self.group is None

    def row(self) -> int:
        return self.parent.children.index(self) if self.parent is not None else 0


def _belongs(node: _Node, provider, prefix: list[str]) -> bool:
    return node.provider is provider and node.path[:len(prefix)] == prefix


_STATE_ROLES = [int(Qt.ItemDataRole.DisplayRole), int(Qt.ItemDataRole.DecorationRole),
                int(Qt.ItemDataRole.ToolTipRole)]


class CatalogTreeModel(QAbstractItemModel):
    operation_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = _Node(name="root", kind=_Kind.ROOT)
        self._provider_connections: dict[int, list[tuple]] = {}
        self._loading_uuids: set[str] = set()
        self._containers: dict[tuple[int, str | None], _Node] = {}   # group -> where its content goes
        self._placements: dict[tuple[int, str | None], Placement] = {}
        self._explicit: dict[int, set[tuple[str, ...]]] = {}         # folders a provider announced
        self._registry = CatalogRegistry.instance()
        self._insert_section(Section.MINE)  # always shown: where new catalogues go

        for provider in self._registry.providers():
            try:
                self._add_provider(provider)
            except (RuntimeError, AttributeError):
                pass  # provider may have been partially destroyed

        self._registry.provider_registered.connect(self._on_provider_registered)
        self._registry.provider_unregistered.connect(self._on_provider_unregistered)
        catalog_color_changed.connect(self._on_catalog_color_changed)

    # ---- indexes ----

    def _index_of(self, node: _Node) -> QModelIndex:
        if node is self._root:
            return QModelIndex()
        return self.createIndex(node.row(), 0, node)

    def _insert(self, parent: _Node, row: int, node: _Node) -> _Node:
        node.parent = parent
        self.beginInsertRows(self._index_of(parent), row, row)
        parent.children.insert(row, node)
        self.endInsertRows()
        return node

    def _remove(self, node: _Node) -> None:
        parent = node.parent
        row = parent.children.index(node)
        self.beginRemoveRows(self._index_of(parent), row, row)
        parent.children.pop(row)
        self.endRemoveRows()

    # ---- sections ----

    def _section_node(self, section: Section) -> _Node | None:
        return next((c for c in self._root.children if c.kind == _Kind.SECTION and c.section == section), None)

    def _insert_section(self, section: Section) -> _Node:
        found = self._section_node(section)
        if found is not None:
            return found
        before = SECTION_ORDER[SECTION_ORDER.index(section) + 1:]
        row = next((i for i, c in enumerate(self._root.children) if c.section in before), len(self._root.children))
        return self._insert(self._root, row, _Node(SECTION_LABELS[section], kind=_Kind.SECTION, section=section))

    def _hide_if_empty(self, node: _Node | None) -> None:
        if node is not None and node.kind == _Kind.SECTION and node.section != Section.MINE and not node.children:
            self._remove(node)

    # ---- groups: where a provider's catalogues go ----

    @staticmethod
    def _splits(provider: CatalogProvider) -> bool:
        return provider.placement(None) is None

    def _group_of(self, provider: CatalogProvider, path: list[str]) -> str | None:
        return path[0] if path and self._splits(provider) else None

    def _placement(self, provider: CatalogProvider, group: str | None) -> Placement:
        found = provider.placement(group)
        return found if found is not None else FALLBACK

    def _container(self, provider: CatalogProvider, group: str | None) -> _Node:
        key = (id(provider), group)
        if key in self._containers:
            return self._containers[key]
        placement = self._placement(provider, group)
        section = self._insert_section(placement.section)
        prefix = [] if group is None else [group]
        if placement.inline:
            container = section
        else:
            node = _Node(self._group_label(provider, group), kind=_Kind.GROUP, provider=provider, path=prefix,
                         is_explicit_folder=group is not None, section=placement.section, group=group)
            container = self._insert(section, self._group_row(section, node.name), node)
        self._containers[key], self._placements[key] = container, placement
        self._sync_placeholders(container, provider, prefix)
        return container

    @staticmethod
    def _group_label(provider: CatalogProvider, group: str | None) -> str:
        if group is None:
            return provider.name
        return provider.folder_display_name([group]) or group

    @staticmethod
    def _group_row(section: _Node, name: str) -> int:
        """Groups sort by name, after the inline content and before the creation rows."""
        for i, c in enumerate(section.children):
            if c.kind == _Kind.PLACEHOLDER or (c.kind == _Kind.GROUP and c.name.casefold() > name.casefold()):
                return i
        return len(section.children)

    @staticmethod
    def _content_row(node: _Node) -> int:
        """Before any group and creation row: notes stay first, then the content."""
        return next((i for i, c in enumerate(node.children) if c.kind in (_Kind.GROUP, _Kind.PLACEHOLDER)),
                    len(node.children))

    def _drop_group(self, provider: CatalogProvider, group: str | None) -> None:
        key = (id(provider), group)
        container = self._containers.pop(key, None)
        self._placements.pop(key, None)
        if container is None:
            return
        if container.kind == _Kind.SECTION:
            prefix = [] if group is None else [group]
            for node in [c for c in container.children if c.kind != _Kind.NOTE and _belongs(c, provider, prefix)]:
                self._remove(node)
            self._hide_if_empty(container)
        else:
            section = container.parent
            self._remove(container)
            self._hide_if_empty(section)

    def _group_placeholders_allowed(self, provider: CatalogProvider, path: list[str]) -> bool:
        placement = self._placements.get((id(provider), self._group_of(provider, path)))
        return (placement is not None and placement.can_create
                and Capability.CREATE_CATALOGS in provider.capabilities())

    # ---- folders and catalogues ----

    def _folder_under(self, node: _Node, provider, segment: str) -> _Node | None:
        return next((c for c in node.children if c.kind == _Kind.FOLDER and c.provider is provider
                     and c.name == segment), None)

    def _walk(self, provider: CatalogProvider, path: list[str], explicit: bool = False) -> _Node:
        """The node holding *path*'s content, its folders made on the way."""
        group = self._group_of(provider, path)
        node = self._container(provider, group)
        prefix = [] if group is None else [group]
        for depth in range(len(prefix), len(path)):
            folder = self._folder_under(node, provider, path[depth])
            if folder is None:
                folder = self._insert(node, self._content_row(node),
                                      _Node(path[depth], kind=_Kind.FOLDER, provider=provider, path=path[:depth + 1]))
                self._sync_placeholders(folder, provider, folder.path)
            node = folder
        if explicit and node.kind == _Kind.FOLDER:
            node.is_explicit_folder = True
        return node

    def _place_catalog(self, provider: CatalogProvider, catalog: Catalog) -> None:
        if self._find_catalog_node(provider, catalog) is not None:
            return
        node = self._walk(provider, list(catalog.path))
        self._insert(node, self._content_row(node),
                     _Node(catalog.name, kind=_Kind.CATALOG, provider=provider, path=list(catalog.path),
                           catalog=catalog))

    def _find_catalog_node(self, provider_or_node, catalog: object) -> _Node | None:
        """The catalogue's node. Takes a provider (or, as before sections, any node to search under)."""
        if isinstance(provider_or_node, _Node):
            return self._find_node_by_uuid(provider_or_node, catalog.uuid)
        return self._find(self._root, lambda n: n.catalog is not None and n.provider is provider_or_node
                          and n.catalog.uuid == catalog.uuid)

    def _find_node_by_uuid(self, node: _Node, uuid: str) -> _Node | None:
        return self._find(node, lambda n: n.catalog is not None and n.catalog.uuid == uuid)

    def _find(self, node: _Node, matches) -> _Node | None:
        for child in node.children:
            if matches(child):
                return child
            found = self._find(child, matches)
            if found is not None:
                return found
        return None

    def _nodes_of(self, provider: CatalogProvider, node: _Node | None = None) -> list[_Node]:
        node = node or self._root
        found = []
        for child in node.children:
            if child.provider is provider:
                found.append(child)
            found.extend(self._nodes_of(provider, child))
        return found

    def _remove_catalog_node(self, node: _Node) -> None:
        parent = node.parent
        self._remove(node)
        self._prune_if_empty(parent)

    def _prune_if_empty(self, node: _Node) -> None:
        """An implicit folder left with no catalogue goes; groups, sections and announced folders stay."""
        if node.kind != _Kind.FOLDER or node.is_explicit_folder:
            return
        if any(not c.is_placeholder for c in node.children):
            return
        parent = node.parent
        self._remove(node)
        self._prune_if_empty(parent)

    # ---- placeholders ----

    def _sync_placeholders(self, node: _Node, provider: CatalogProvider, path: list[str]) -> None:
        mine = [c for c in node.children if c.is_placeholder and c.provider is provider]
        if self._group_placeholders_allowed(provider, path):
            if not mine:
                for kind, text in ((_PlaceholderType.CATALOG, "New catalog…"), (_PlaceholderType.FOLDER, "New folder…")):
                    self._insert(node, len(node.children),
                                 _Node(text, kind=_Kind.PLACEHOLDER, provider=provider, path=path, placeholder_type=kind))
        else:
            for placeholder in mine:
                self._remove(placeholder)

    def _sync_all_placeholders(self, provider: CatalogProvider) -> None:
        for (pid, group), container in list(self._containers.items()):
            if pid != id(provider):
                continue
            prefix = [] if group is None else [group]
            self._sync_placeholders(container, provider, prefix)
            for folder in self._nodes_of(provider, container):
                if folder.kind == _Kind.FOLDER:
                    self._sync_placeholders(folder, provider, folder.path)

    # ---- notes ----

    def _sync_notes(self, provider: CatalogProvider) -> None:
        for section in SECTION_ORDER:
            text = provider.section_note(section)
            node = self._section_node(section)
            note = next((c for c in node.children if c.kind == _Kind.NOTE and c.provider is provider), None) \
                if node is not None else None
            if note is not None and note.name == text:
                continue
            if note is not None:
                self._remove(note)
            if text:
                node = self._insert_section(section)
                self._insert(node, 0, _Node(text, kind=_Kind.NOTE, provider=provider, section=section))
            self._hide_if_empty(self._section_node(section))

    # ---- providers ----

    def _add_provider(self, provider: CatalogProvider) -> None:
        self._populate(provider)
        on_added = lambda cat, p=provider: self._place_catalog(p, cat)
        on_removed = lambda cat, p=provider: self._on_catalog_removed(p, cat)
        on_dirty = lambda cat, dirty, p=provider: self._on_dirty_changed(p, cat)
        on_renamed = lambda cat, p=provider: self._on_catalog_renamed(p, cat)
        on_moved = lambda cat, p=provider: self._on_catalog_moved(p, cat)
        on_folder_added = lambda path, p=provider: self._on_folder_added(p, path)
        on_folder_removed = lambda path, p=provider: self._on_folder_removed(p, path)
        on_status = lambda p=provider: self._on_provider_status_changed(p)
        on_caps = lambda cat, p=provider: self._on_capabilities_changed(p)
        on_load_start = lambda cat, p=provider: self._on_loading_changed(p, cat, True)
        on_load_end = lambda cat, p=provider: self._on_loading_changed(p, cat, False)
        connections = [
            (provider.catalog_added, on_added), (provider.catalog_removed, on_removed),
            (provider.dirty_changed, on_dirty), (provider.catalog_renamed, on_renamed),
            (provider.catalog_moved, on_moved), (provider.folder_added, on_folder_added),
            (provider.folder_removed, on_folder_removed), (provider.status_changed, on_status),
            (provider.capabilities_changed, on_caps), (provider.loading_started, on_load_start),
            (provider.loading_finished, on_load_end),
        ]
        for signal, slot in connections:
            signal.connect(slot)
        self._provider_connections[id(provider)] = connections

    def _populate(self, provider: CatalogProvider) -> None:
        if not self._splits(provider):
            self._container(provider, None)  # its node shows even before it has catalogues
        for path in sorted(self._explicit.get(id(provider), ())):
            self._walk(provider, list(path), explicit=True)
        for catalog in provider.catalogs():
            self._place_catalog(provider, catalog)
        self._sync_notes(provider)

    def _clear(self, provider: CatalogProvider) -> None:
        for pid, group in [k for k in self._containers if k[0] == id(provider)]:
            self._drop_group(provider, group)
        for node in self._nodes_of(provider):
            if node.parent is not None and node in node.parent.children:
                section = node.parent if node.parent.kind == _Kind.SECTION else None
                self._remove(node)
                self._hide_if_empty(section)

    def _provider_node(self, provider: CatalogProvider) -> _Node | None:
        """The provider's own node, when it is placed as a whole."""
        return self._containers.get((id(provider), None)) if not self._splits(provider) else None

    def creation_placeholder(self, provider: CatalogProvider) -> _Node | None:
        """The "New catalog…" row where the provider's new catalogues go: My catalogues first."""
        rows = [n for n in self._nodes_of(provider) if n.placeholder_type == _PlaceholderType.CATALOG]
        return min(rows, key=lambda n: (SECTION_ORDER.index(self._section_of(n)), len(n.path)), default=None)

    def _section_of(self, node: _Node) -> Section:
        while node.kind != _Kind.SECTION:
            node = node.parent
        return node.section

    # ---- slots ----

    def _on_provider_registered(self, provider: object) -> None:
        try:
            provider.catalogs()  # may fail if __init__ hasn't finished
        except (RuntimeError, AttributeError):
            return
        self._add_provider(provider)

    def _on_provider_unregistered(self, provider: object) -> None:
        for signal, slot in self._provider_connections.pop(id(provider), []):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._clear(provider)
        self._explicit.pop(id(provider), None)

    def _emit_changed(self, node: _Node, roles: list[int]) -> None:
        index = self._index_of(node)
        self.dataChanged.emit(index, index, roles)

    def _on_dirty_changed(self, provider: CatalogProvider, catalog: object) -> None:
        if catalog is not None:
            node = self._find_catalog_node(provider, catalog)
            if node is not None:
                self._emit_changed(node, [int(Qt.ItemDataRole.DisplayRole)])
        provider_node = self._provider_node(provider)
        if provider_node is not None:
            self._emit_changed(provider_node, [int(Qt.ItemDataRole.DisplayRole), DIRTY_PROVIDER_ROLE])

    def _on_catalog_color_changed(self, uuid: str) -> None:
        node = self._find_node_by_uuid(self._root, uuid)
        if node is not None:
            self._emit_changed(node, [int(Qt.ItemDataRole.DecorationRole)])

    def _on_catalog_renamed(self, provider: CatalogProvider, catalog: object) -> None:
        node = self._find_catalog_node(provider, catalog)
        if node is not None:
            node.name = catalog.name
            self._emit_changed(node, [int(Qt.ItemDataRole.DisplayRole)])

    def _on_catalog_moved(self, provider: CatalogProvider, catalog: object) -> None:
        """The catalogue's path was already changed by the provider."""
        node = self._find_catalog_node(provider, catalog)
        if node is None:
            return
        self._remove_catalog_node(node)
        self._place_catalog(provider, catalog)

    def _on_catalog_removed(self, provider: CatalogProvider, catalog: object) -> None:
        node = self._find_catalog_node(provider, catalog)
        if node is not None:
            self._remove_catalog_node(node)

    def _on_folder_added(self, provider: CatalogProvider, path: list) -> None:
        self._explicit.setdefault(id(provider), set()).add(tuple(path))
        node = self._walk(provider, list(path), explicit=True)
        self._sync_placeholders(node, provider, list(path))  # announced again once it can create

    def _on_folder_removed(self, provider: CatalogProvider, path: list) -> None:
        path = list(path)
        self._explicit.get(id(provider), set()).discard(tuple(path))
        if len(path) == 1 and self._splits(provider):
            return self._drop_group(provider, path[0])
        node = self._find(self._root, lambda n: n.kind == _Kind.FOLDER and n.provider is provider and n.path == path)
        if node is not None:
            self._remove(node)

    def _on_loading_changed(self, provider: CatalogProvider, catalog: object, loading: bool) -> None:
        (self._loading_uuids.add if loading else self._loading_uuids.discard)(catalog.uuid)
        node = self._find_catalog_node(provider, catalog)
        if node is not None:
            self._emit_changed(node, [LOADING_ROLE])

    def _on_provider_status_changed(self, provider: CatalogProvider) -> None:
        """Names, icons and notes may follow the provider's state (signed in, synced...)."""
        self._sync_notes(provider)
        for (pid, group), container in self._containers.items():
            if pid == id(provider) and container.kind == _Kind.GROUP:
                container.name = self._group_label(provider, group)
        self._repaint(self._root)

    def _repaint(self, node: _Node) -> None:
        if not node.children:
            return
        parent = self._index_of(node)
        self.dataChanged.emit(self.index(0, 0, parent), self.index(len(node.children) - 1, 0, parent), _STATE_ROLES)
        for child in node.children:
            self._repaint(child)

    def _on_capabilities_changed(self, provider: CatalogProvider) -> None:
        """A role change can move a project to another section, or take its creation rows away."""
        moved = any(self._placement(provider, group) != placement
                    for (pid, group), placement in self._placements.items() if pid == id(provider))
        if moved:
            self._clear(provider)
            self._populate(provider)
        else:
            self._sync_all_placeholders(provider)
        self._on_provider_status_changed(provider)

    # ---- QAbstractItemModel interface ----

    def node_from_index(self, index: QModelIndex) -> _Node:
        return index.internalPointer() if index.isValid() else self._root

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        return self.createIndex(row, column, self.node_from_index(parent).children[row])

    def parent(self, index: QModelIndex = None) -> QModelIndex:
        if index is None or not index.isValid():
            return QModelIndex()
        parent_node = index.internalPointer().parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        return self.createIndex(parent_node.row(), 0, parent_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.node_from_index(parent).children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def _folder_path(self, node: _Node) -> list[str]:
        """The node's path in its provider."""
        return list(node.path)

    def inline_groups(self, section_node: _Node) -> list[tuple[CatalogProvider, list[str]]]:
        """The groups shown directly in a section: (provider, path of the group)."""
        return [(self._provider_by_id(pid), [] if group is None else [group])
                for (pid, group), container in self._containers.items() if container is section_node]

    @staticmethod
    def is_section(node: _Node) -> bool:
        return node.kind == _Kind.SECTION

    def providers_in(self, section_node: _Node) -> list[CatalogProvider]:
        """The providers that place their folders one by one and show something in this section:
        their provider-level actions go on its header, as they have no node of their own."""
        found = []
        for node in section_node.children:
            if node.provider is not None and node.provider not in found and self._splits(node.provider):
                found.append(node.provider)
        for provider, _ in self.inline_groups(section_node):
            if provider not in found:
                found.append(provider)
        return found

    def _provider_by_id(self, pid: int) -> CatalogProvider:
        return next(p for p in self._registry.providers() if id(p) == pid)

    def _node_type(self, node: _Node) -> NodeType:
        if node.catalog is not None:
            return NodeType.CATALOG
        if node.is_provider_node:
            return NodeType.PROVIDER
        return NodeType.FOLDER

    def _ask_provider(self, node: _Node):
        """(provider, node type, folder path) a section asks its inline group about, else the node's own."""
        if node.kind == _Kind.SECTION:
            inline = self.inline_groups(node)
            if len(inline) != 1:
                return None
            provider, path = inline[0]
            return provider, (NodeType.FOLDER if path else NodeType.PROVIDER), (path or None)
        if node.provider is None or node.kind in (_Kind.PLACEHOLDER, _Kind.NOTE):
            return None
        node_type = self._node_type(node)
        return node.provider, node_type, (node.path if node_type == NodeType.FOLDER else None)

    def _tooltip(self, node: _Node) -> str | None:
        asked = self._ask_provider(node)
        if asked is None:
            return SECTION_TIPS.get(node.section) if node.kind == _Kind.SECTION else None
        provider, node_type, path = asked
        custom = provider.node_tooltip(node_type, path=path, catalog=node.catalog)
        if custom is None and node_type == NodeType.PROVIDER:
            custom = provider.description or None
        if node.kind not in (_Kind.SECTION, _Kind.GROUP) or node.is_provider_node or custom is None:
            return custom  # a provider's own node is named after it already
        return _with_provider_name(custom, provider.name)

    def _display(self, node: _Node) -> str:
        if node.kind in (_Kind.SECTION, _Kind.NOTE, _Kind.PLACEHOLDER) or node.provider is None:
            return node.name
        name = node.name
        if node.kind == _Kind.FOLDER and node.is_explicit_folder:
            name = node.provider.folder_display_name(node.path) or name
        if Capability.SAVE in node.provider.capabilities():
            if node.catalog is not None and node.provider.is_dirty(node.catalog):
                name += " *"
            elif node.is_provider_node and node.provider.is_dirty():
                name += " *"
        return name

    def _icon(self, node: _Node):
        from ...theming.icons import get_icon
        if node.kind in (_Kind.PLACEHOLDER, _Kind.NOTE):
            return None
        asked = self._ask_provider(node)
        if asked is not None:
            provider, node_type, path = asked
            custom = provider.node_icon(node_type, path)
            if custom is not None:
                return custom
        if node.kind == _Kind.SECTION:
            return get_icon(SECTION_ICONS[node.section])
        if node.catalog is not None:
            from ..backend.color_palette import catalog_swatch_icon
            return catalog_swatch_icon(node.catalog.uuid)
        return get_icon("dataSourceRoot" if node.is_provider_node else "folder_open")

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        node = index.internalPointer()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(node)
        if role == Qt.ItemDataRole.FontRole:
            return _font(node)
        if role == Qt.ItemDataRole.ForegroundRole and node.kind in (_Kind.PLACEHOLDER, _Kind.NOTE):
            from PySide6.QtGui import QColor
            return QColor(128, 128, 128)
        if role == Qt.ItemDataRole.DecorationRole:
            return self._icon(node)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(node)
        if role == DIRTY_PROVIDER_ROLE:
            return (node.is_provider_node and Capability.SAVE in node.provider.capabilities()
                    and node.provider.is_dirty())
        if role == LOADING_ROLE:
            return node.catalog is not None and node.catalog.uuid in self._loading_uuids
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        node = index.internalPointer()
        name = value.strip() if isinstance(value, str) else str(value).strip()
        if not name:
            return False
        if node.placeholder_type == _PlaceholderType.CATALOG:
            node.provider.create_catalog(name, path=list(node.path) or None)
            return True
        if node.placeholder_type == _PlaceholderType.FOLDER:
            parent = node.parent
            folder = self._insert(parent, self._content_row(parent),
                                  _Node(name, kind=_Kind.FOLDER, provider=node.provider, path=[*node.path, name]))
            self._sync_placeholders(folder, node.provider, folder.path)
            return True
        if node.catalog is not None and Capability.RENAME_CATALOG in node.provider.capabilities():
            node.provider.rename_catalog(node.catalog, name)
            node.name = name
            self.dataChanged.emit(index, index, [int(Qt.ItemDataRole.DisplayRole)])
            return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        node = index.internalPointer()
        if node.kind == _Kind.NOTE:
            return Qt.ItemFlag.ItemIsEnabled
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if node.is_placeholder:
            return base | Qt.ItemFlag.ItemIsEditable
        if node.catalog is not None:
            base |= Qt.ItemFlag.ItemIsDragEnabled
            if Capability.RENAME_CATALOG in node.provider.capabilities(node.catalog):
                base |= Qt.ItemFlag.ItemIsEditable
        target = self._drop_target(node)
        if target is not None and self._accepts_catalogs(target[0]):
            base |= Qt.ItemFlag.ItemIsDropEnabled
        return base

    @staticmethod
    def _accepts_catalogs(provider: CatalogProvider) -> bool:
        caps = provider.capabilities()
        return Capability.CREATE_CATALOGS in caps or Capability.MOVE_CATALOG in caps

    # ---- drag and drop ----

    def mimeTypes(self) -> list[str]:
        from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE
        return [CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE]

    def mimeData(self, indexes):
        from SciQLop.core.mime import encode_mime
        catalogs, seen = [], set()
        for idx in indexes:
            node = idx.internalPointer() if idx.isValid() else None
            if node is not None and node.catalog is not None and node.catalog.uuid not in seen:
                catalogs.append(node.catalog)
                seen.add(node.catalog.uuid)
        return encode_mime(catalogs) if catalogs else None

    def supportedDropActions(self) -> Qt.DropAction:
        # LinkAction is only ever offered for event drops (the event table declares it).
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction | Qt.DropAction.LinkAction

    def supportedDragActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def _drop_target(self, node: _Node) -> tuple[CatalogProvider, list[str]] | None:
        """(provider, path) a catalogue dropped on *node* goes to. On a section: its inline group,
        so My catalogues takes a drop and Reference refuses one."""
        if node.kind in (_Kind.PLACEHOLDER, _Kind.NOTE, _Kind.ROOT):
            return None
        if node.catalog is not None:
            node = node.parent
        if node.kind == _Kind.SECTION:
            inline = self.inline_groups(node)
            return inline[0] if len(inline) == 1 else None
        return (node.provider, list(node.path)) if node.provider is not None else None

    def _resolve_drop_target(self, parent: QModelIndex):
        return self._drop_target(parent.internalPointer()) if parent.isValid() else None

    def canDropMimeData(self, data, action, row, column, parent) -> bool:
        from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE
        if data.hasFormat(EVENT_LIST_MIME_TYPE):
            node = parent.internalPointer() if parent.isValid() else None
            if node is None or node.catalog is None:
                return False
            caps = node.provider.capabilities(node.catalog)
            return Capability.CREATE_EVENTS in caps or Capability.EDIT_EVENTS in caps
        if not data.hasFormat(CATALOG_LIST_MIME_TYPE):
            return False
        target = self._resolve_drop_target(parent)
        return target is not None and self._accepts_catalogs(target[0])

    def dropMimeData(self, data, action, row, column, parent) -> bool:
        from SciQLop.core.mime import decode_mime
        from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE
        from SciQLop.components.sciqlop_logging import getLogger
        log = getLogger(__name__)
        if action == Qt.DropAction.IgnoreAction:
            return True
        if data.hasFormat(EVENT_LIST_MIME_TYPE):
            return self._drop_events(data, action, parent, log)
        catalogs = decode_mime(data)
        target = self._resolve_drop_target(parent)
        if not catalogs or target is None:
            return False
        provider, path = target
        for source in catalogs:
            try:
                self._drop_catalog(source, provider, path)
            except Exception as e:
                log.warning("Catalog drop failed for %r → %r: %s", source.name, path, e)
                self.operation_failed.emit(f"Could not move/copy catalog '{source.name}': {e}")
        # False, so Qt does not also call removeRows() on the source: provider signals update the tree.
        return False

    def _drop_catalog(self, source: Catalog, provider: CatalogProvider, path: list[str]) -> None:
        if source.provider is provider and provider.can_move_catalog(source, path):
            if list(source.path) != path:
                provider.move_catalog(source, path)
            return
        if Capability.CREATE_CATALOGS not in provider.capabilities():
            return
        self._copy_catalog(source, provider, path)

    def _copy_catalog(self, source: Catalog, provider: CatalogProvider, path: list[str]) -> None:
        import uuid as _uuid
        from ..backend.provider import CatalogEvent
        copy = provider.create_catalog(self._unique_catalog_name(provider, path, source.name), path=path)
        for event in (source.provider.events(source) if source.provider else []):
            provider.add_event(copy, CatalogEvent(uuid=str(_uuid.uuid4()), start=event.start, stop=event.stop,
                                                  meta=dict(event.meta)))

    _DROP_ACTION_NAMES = {
        Qt.DropAction.LinkAction: "link",
        Qt.DropAction.MoveAction: "move",
        Qt.DropAction.CopyAction: "duplicate",
    }

    def _drop_events(self, data, action, parent, log) -> bool:
        from ..backend.event_mime import decode_event_list

        payload = decode_event_list(data)
        if payload is None or not parent.isValid():
            return False
        target_node = parent.internalPointer()
        target_catalog = target_node.catalog
        if target_catalog is None or target_node.provider is None:
            return False

        source_provider = self._registry.provider_by_name(payload.provider)
        source_catalog = None
        source_events = []
        if source_provider is not None and payload.catalog_uuid is not None:
            source_catalog = next((c for c in source_provider.catalogs() if c.uuid == payload.catalog_uuid), None)
            if source_catalog is not None:
                by_uuid = {e.uuid: e for e in source_provider.events(source_catalog)}
                source_events = [by_uuid[u] for u in payload.event_uuids if u in by_uuid]
        if not source_events:
            return False

        # Across providers always duplicate: "move"/"link" would put the source provider's event
        # object in the destination's bookkeeping, which only makes sense within one provider.
        if source_provider is not target_node.provider:
            drop_action = "duplicate"
        elif action in self._DROP_ACTION_NAMES:
            drop_action = self._DROP_ACTION_NAMES[action]
        else:
            # A public entry point: an unknown or composite action fails closed, not as a "link".
            log.warning("Event drop with unrecognized action %r ignored", action)
            return False

        try:
            target_node.provider.handle_event_drop(target_catalog=target_catalog, events=source_events,
                                                   action=drop_action, source_catalog=source_catalog)
        except Exception as e:
            log.warning("Event drop failed: %s", e)
            self.operation_failed.emit(f"Could not {drop_action} event(s): {e}")
        return False

    def _unique_catalog_name(self, provider, sub_path: list[str], base: str) -> str:
        existing = {c.name for c in provider.catalogs() if list(c.path) == list(sub_path)}
        if base not in existing:
            return base
        return next((f"{base} ({i})" for i in range(2, 1000) if f"{base} ({i})" not in existing),
                    f"{base} ({_uuid_short()})")


def _with_provider_name(tip: str, provider_name: str) -> str:
    if tip.lstrip().startswith("<"):
        return f"{tip}<br><i>From {escape(provider_name)}</i>"
    return f"{tip}\nFrom {provider_name}"


def _font(node: _Node):
    if node.kind not in (_Kind.PLACEHOLDER, _Kind.NOTE, _Kind.SECTION):
        return None
    from PySide6.QtGui import QFont
    font = QFont()
    if node.kind == _Kind.SECTION:
        font.setBold(True)
    else:
        font.setItalic(True)
    return font


def _uuid_short() -> str:
    import uuid as _uuid
    return str(_uuid.uuid4())[:8]

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Signal, QRect, QEvent, QItemSelectionModel
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSplitter,
    QStyledItemDelegate,
    QTableView,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
    QMenu,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from datetime import datetime, timezone, timedelta
import uuid as _uuid
from ..backend.provider import Capability, CatalogProvider, Catalog, CatalogEvent
from .catalog_tree import CatalogTreeModel
from .event_table import EventTableModel


class _CatalogFilterProxy(QSortFilterProxyModel):
    """Case-insensitive substring filter that keeps ancestors of matching nodes."""

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True
        idx = self.sourceModel().index(source_row, 0, source_parent)
        name = self.sourceModel().data(idx, Qt.ItemDataRole.DisplayRole) or ""
        if pattern.lower() in name.lower():
            return True
        # Accept if any child matches (recursive)
        for row in range(self.sourceModel().rowCount(idx)):
            if self.filterAcceptsRow(row, idx):
                return True
        return False


class _SaveButtonDelegate(QStyledItemDelegate):
    """Renders a clickable save icon next to dirty provider nodes."""

    save_clicked = Signal(QModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon = None
        self._icon_size = 16

    def _get_icon(self):
        if self._icon is None:
            self._icon = QIcon.fromTheme("document-save")
        return self._icon

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        from .catalog_tree import DIRTY_PROVIDER_ROLE
        if index.data(DIRTY_PROVIDER_ROLE):
            icon_rect = self._icon_rect(option)
            self._get_icon().paint(painter, icon_rect)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        from .catalog_tree import DIRTY_PROVIDER_ROLE
        if index.data(DIRTY_PROVIDER_ROLE):
            size.setWidth(size.width() + self._icon_size + 4)
        return size

    def _icon_rect(self, option):
        return QRect(
            option.rect.right() - self._icon_size - 2,
            option.rect.top() + (option.rect.height() - self._icon_size) // 2,
            self._icon_size,
            self._icon_size,
        )

    def editorEvent(self, event, model, option, index):
        from .catalog_tree import DIRTY_PROVIDER_ROLE
        if index.data(DIRTY_PROVIDER_ROLE):
            if event.type() == QEvent.Type.MouseButtonRelease:
                if self._icon_rect(option).contains(event.pos()):
                    self.save_clicked.emit(index)
                    return True
        return super().editorEvent(event, model, option, index)


class CatalogBrowser(QWidget):
    """Dock-ready widget: tree of providers/catalogs + event table."""

    event_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Catalog Browser")

        self._current_provider: CatalogProvider | None = None
        self._events_changed_provider: CatalogProvider | None = None
        self._current_catalog: Catalog | None = None
        self._panels: list = []

        # --- filter bar ---
        self._filter_bar = QLineEdit()
        self._filter_bar.setPlaceholderText("Filter catalogs...")

        # --- tree view (left) ---
        self._tree_model = CatalogTreeModel()
        self._proxy_model = _CatalogFilterProxy()
        self._proxy_model.setSourceModel(self._tree_model)
        self._catalog_tree = QTreeView()
        self._catalog_tree.setModel(self._proxy_model)
        self._catalog_tree.setHeaderHidden(True)
        self._save_delegate = _SaveButtonDelegate(self._catalog_tree)
        self._save_delegate.save_clicked.connect(self._on_save_clicked)
        self._catalog_tree.setItemDelegate(self._save_delegate)
        self._catalog_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._catalog_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._catalog_tree.doubleClicked.connect(self._on_tree_double_clicked)
        self._catalog_tree.selectionModel().currentChanged.connect(self._on_catalog_selected)
        self._filter_bar.textChanged.connect(self._on_filter_changed)

        # --- event table (right) ---
        self._event_model = EventTableModel()
        self._event_table = QTableView()
        self._event_table.setModel(self._event_model)
        self._event_table.selectionModel().currentChanged.connect(self._on_event_selected)

        # --- event toolbar (above table) ---
        self._add_event_btn = QPushButton("Add Event")
        self._add_event_btn.setVisible(False)
        self._add_event_btn.clicked.connect(self._on_add_event)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(self._on_delete)

        event_toolbar = QHBoxLayout()
        event_toolbar.addWidget(self._add_event_btn)
        event_toolbar.addWidget(self._delete_btn)
        event_toolbar.addStretch()

        event_panel = QWidget()
        event_layout = QVBoxLayout(event_panel)
        event_layout.setContentsMargins(0, 0, 0, 0)
        event_layout.addLayout(event_toolbar)
        event_layout.addWidget(self._event_table, 1)

        # --- splitter ---
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._catalog_tree)
        self._splitter.addWidget(event_panel)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)

        # --- actions toolbar (bottom) ---
        self._actions_btn = QToolButton()
        self._actions_btn.setText("Actions")
        self._actions_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._actions_menu = QMenu(self._actions_btn)
        self._actions_btn.setMenu(self._actions_menu)
        self._actions_btn.setVisible(False)

        actions_toolbar = QHBoxLayout()
        actions_toolbar.addStretch()
        actions_toolbar.addWidget(self._actions_btn)

        # --- layout ---
        layout = QVBoxLayout(self)
        layout.addWidget(self._filter_bar)
        layout.addWidget(self._splitter, 1)
        layout.addLayout(actions_toolbar)

    # ---- slots ----

    def _on_filter_changed(self, text: str) -> None:
        self._proxy_model.setFilterFixedString(text)
        if text:
            self._catalog_tree.expandAll()

    def _on_tree_double_clicked(self, proxy_index: QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(proxy_index)
        node = self._tree_model.node_from_index(source_index)
        if node.is_placeholder or (node.catalog is not None and
                self._tree_model.flags(source_index) & Qt.ItemFlag.ItemIsEditable):
            self._catalog_tree.edit(proxy_index)

    def _on_catalog_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(current)
        node = self._tree_model.node_from_index(source_index)
        if node is self._tree_model._root or node.is_placeholder:
            return
        # Disconnect from previously connected provider
        if self._events_changed_provider is not None:
            try:
                self._events_changed_provider.events_changed.disconnect(self._on_events_changed)
            except RuntimeError:
                pass
            self._events_changed_provider = None
        if node.catalog is not None:
            self._current_provider = node.provider
            self._current_catalog = node.catalog
            events = node.provider.events(node.catalog)
            self._event_model.set_events(events)
            node.provider.events_changed.connect(self._on_events_changed)
            self._events_changed_provider = node.provider
        else:
            self._current_provider = node.provider
            self._current_catalog = None
            self._event_model.clear()
        self._update_toolbar()

    def _on_event_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        if current.isValid():
            event = self._event_model.event_at(current.row())
            if event is not None:
                self.event_selected.emit(event)

    def _on_events_changed(self, catalog: Catalog) -> None:
        """Refresh event table when async loading completes for the selected catalog."""
        if self._current_catalog is not None and catalog.uuid == self._current_catalog.uuid:
            events = self._current_provider.events(self._current_catalog)
            self._event_model.set_events(events)

    def _update_toolbar(self) -> None:
        if self._current_provider is None:
            self._add_event_btn.setVisible(False)
            self._delete_btn.setVisible(False)
            self._actions_btn.setVisible(False)
            return

        caps = self._current_provider.capabilities(self._current_catalog)
        self._add_event_btn.setVisible(Capability.CREATE_EVENTS in caps)
        self._delete_btn.setVisible(Capability.DELETE_EVENTS in caps)

        # Populate custom actions menu
        self._actions_menu.clear()
        actions = self._current_provider.actions(self._current_catalog)
        self._actions_btn.setVisible(len(actions) > 0)
        for action in actions:
            menu_action = self._actions_menu.addAction(action.name)
            if action.icon is not None:
                menu_action.setIcon(action.icon)
            cat = self._current_catalog
            menu_action.triggered.connect(lambda checked, cb=action.callback, c=cat: cb(c))

    def highlight_event(self, event) -> None:
        """Select the row in the event table matching the given event."""
        row = self._event_model.row_for_event(event)
        if row >= 0:
            index = self._event_model.index(row, 0)
            self._event_table.selectionModel().setCurrentIndex(
                index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
            )

    def connect_to_panel(self, panel) -> None:
        """Wire bidirectional event selection between this browser and a panel."""
        if panel in self._panels:
            return
        self._panels.append(panel)
        manager = panel.catalog_manager
        self.event_selected.connect(manager.select_event)
        manager.event_clicked.connect(self.highlight_event)
        panel.destroyed.connect(lambda: self._on_panel_destroyed(panel))

    def _on_panel_destroyed(self, panel) -> None:
        if panel in self._panels:
            self._panels.remove(panel)

    def disconnect_from_panel(self, panel) -> None:
        """Remove bidirectional event selection wiring for a panel."""
        if panel not in self._panels:
            return
        self._panels.remove(panel)
        manager = panel.catalog_manager
        try:
            self.event_selected.disconnect(manager.select_event)
        except RuntimeError:
            pass
        try:
            manager.event_clicked.disconnect(self.highlight_event)
        except RuntimeError:
            pass

    def _on_add_event(self) -> None:
        if self._current_provider is None or self._current_catalog is None:
            return
        caps = self._current_provider.capabilities(self._current_catalog)
        if Capability.CREATE_EVENTS not in caps:
            return
        # Use the first connected panel's visible range to place the new event
        if self._panels:
            tr = self._panels[0].time_range
            center = (tr.start() + tr.stop()) / 2.0
            half_span = (tr.stop() - tr.start()) * 0.05  # 10% of visible range
            start = datetime.fromtimestamp(center - half_span, tz=timezone.utc)
            stop = datetime.fromtimestamp(center + half_span, tz=timezone.utc)
        else:
            now = datetime.now(tz=timezone.utc)
            start = now - timedelta(minutes=30)
            stop = now + timedelta(minutes=30)
        event = CatalogEvent(
            uuid=str(_uuid.uuid4()),
            start=start,
            stop=stop,
        )
        self._current_provider.add_event(self._current_catalog, event)
        # Refresh event table
        events = self._current_provider.events(self._current_catalog)
        self._event_model.set_events(events)

    def _on_delete(self) -> None:
        if self._current_provider is None:
            return
        selected = self._event_table.selectionModel().currentIndex()
        if selected.isValid() and self._current_catalog is not None:
            event = self._event_model.event_at(selected.row())
            if event is not None:
                caps = self._current_provider.capabilities(self._current_catalog)
                if Capability.DELETE_EVENTS in caps:
                    self._current_provider.remove_event(self._current_catalog, event)
                    events = self._current_provider.events(self._current_catalog)
                    self._event_model.set_events(events)
                    return

    def _on_save_clicked(self, proxy_index: QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(proxy_index)
        node = self._tree_model.node_from_index(source_index)
        if node.provider is not None:
            node.provider.save()

    def _folder_path(self, node) -> list[str]:
        """Build the path segments from provider node down to this folder node."""
        segments = []
        n = node
        while n.parent is not None and n.parent.parent is not None:
            # stop at provider node (whose parent is root)
            segments.append(n.name)
            n = n.parent
        segments.reverse()
        return segments

    def _trigger_placeholder_edit(self, placeholder_node) -> None:
        """Clear filter and trigger inline edit on a placeholder node."""
        self._filter_bar.clear()
        source_index = self._tree_model.createIndex(placeholder_node.row(), 0, placeholder_node)
        proxy_index = self._proxy_model.mapFromSource(source_index)
        if proxy_index.isValid():
            self._catalog_tree.edit(proxy_index)

    def _on_tree_context_menu(self, pos) -> None:
        proxy_index = self._catalog_tree.indexAt(pos)
        if not proxy_index.isValid():
            return
        source_index = self._proxy_model.mapToSource(proxy_index)
        node = self._tree_model.node_from_index(source_index)
        if node.provider is None:
            return

        caps = node.provider.capabilities()
        menu = QMenu(self)

        # Provider-level actions (provider node = parent is root)
        if node.parent is self._tree_model._root:
            for action in node.provider.actions(None):
                a = menu.addAction(action.name)
                if action.icon is not None:
                    a.setIcon(action.icon)
                a.triggered.connect(lambda checked, cb=action.callback: cb(None))

        # Explicit folder actions (room nodes)
        if node.is_explicit_folder:
            path = self._folder_path(node)
            for action in node.provider.folder_actions(path):
                a = menu.addAction(action.name)
                if action.icon is not None:
                    a.setIcon(action.icon)
                a.triggered.connect(lambda checked, cb=action.callback, p=path: cb(p))

        # Creation actions (folder or provider node, gated on CREATE_CATALOGS)
        if node.catalog is None and not node.is_placeholder:
            if Capability.CREATE_CATALOGS in caps:
                from .catalog_tree import _PlaceholderType
                cat_ph = next((c for c in node.children if c.placeholder_type == _PlaceholderType.CATALOG), None)
                folder_ph = next((c for c in node.children if c.placeholder_type == _PlaceholderType.FOLDER), None)
                if cat_ph is not None:
                    new_cat_action = menu.addAction("New Catalog")
                    new_cat_action.triggered.connect(lambda checked, ph=cat_ph: self._trigger_placeholder_edit(ph))
                if folder_ph is not None:
                    new_folder_action = menu.addAction("New Folder")
                    new_folder_action.triggered.connect(lambda checked, ph=folder_ph: self._trigger_placeholder_edit(ph))

        if Capability.SAVE in caps and node.provider.is_dirty():
            if (node.catalog is not None
                    and Capability.SAVE_CATALOG in caps
                    and node.provider.is_dirty(node.catalog)):
                save_action = menu.addAction("Save Catalog")
                save_action.triggered.connect(lambda: node.provider.save_catalog(node.catalog))
            else:
                save_action = menu.addAction("Save")
                save_action.triggered.connect(lambda: node.provider.save())

        if node.catalog is not None and Capability.DELETE_CATALOGS in caps:
            delete_action = menu.addAction("Delete Catalog")
            delete_action.triggered.connect(lambda: self._delete_catalog(node))

        if menu.isEmpty():
            return
        menu.exec(self._catalog_tree.viewport().mapToGlobal(pos))

    def _delete_catalog(self, node) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Delete Catalog",
            f"Delete catalog '{node.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._current_catalog is not None and self._current_catalog.uuid == node.catalog.uuid:
                self._current_catalog = None
                self._event_model.clear()
                self._update_toolbar()
            node.provider.remove_catalog(node.catalog)


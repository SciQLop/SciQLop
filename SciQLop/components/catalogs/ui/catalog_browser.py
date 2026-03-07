from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
    QMenu,
)
from PySide6.QtCore import Qt

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


class CatalogBrowser(QWidget):
    """Dock-ready widget: tree of providers/catalogs + event table."""

    event_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Catalog Browser")

        self._current_provider: CatalogProvider | None = None
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

    def _on_catalog_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(current)
        node = self._tree_model.node_from_index(source_index)
        # Disconnect from previous provider's events_changed
        if self._current_provider is not None:
            try:
                self._current_provider.events_changed.disconnect(self._on_events_changed)
            except RuntimeError:
                pass
        if node.catalog is not None:
            self._current_provider = node.provider
            self._current_catalog = node.catalog
            events = node.provider.events(node.catalog)
            self._event_model.set_events(events)
            # Listen for async event loading
            node.provider.events_changed.connect(self._on_events_changed)
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
            from PySide6.QtCore import QItemSelectionModel
            self._event_table.selectionModel().setCurrentIndex(
                index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
            )

    def connect_to_panel(self, panel) -> None:
        """Wire bidirectional event selection between this browser and a panel."""
        self._panels.append(panel)
        manager = panel.catalog_manager
        self.event_selected.connect(manager.select_event)
        manager.event_clicked.connect(self.highlight_event)

    def disconnect_from_panel(self, panel) -> None:
        """Remove bidirectional event selection wiring for a panel."""
        if panel in self._panels:
            self._panels.remove(panel)
        manager = panel.catalog_manager
        self.event_selected.disconnect(manager.select_event)
        manager.event_clicked.disconnect(self.highlight_event)

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

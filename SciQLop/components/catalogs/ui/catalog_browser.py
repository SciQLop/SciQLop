from __future__ import annotations

from PySide6.QtCore import QModelIndex, Signal
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

from ..backend.provider import Capability, CatalogProvider, Catalog
from .catalog_tree import CatalogTreeModel
from .event_table import EventTableModel


class CatalogBrowser(QWidget):
    """Dock-ready widget: tree of providers/catalogs + event table."""

    event_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._current_provider: CatalogProvider | None = None
        self._current_catalog: Catalog | None = None

        # --- filter bar ---
        self._filter_bar = QLineEdit()
        self._filter_bar.setPlaceholderText("Filter catalogs...")

        # --- tree view (left) ---
        self._tree_model = CatalogTreeModel()
        self._catalog_tree = QTreeView()
        self._catalog_tree.setModel(self._tree_model)
        self._catalog_tree.setHeaderHidden(True)
        self._catalog_tree.selectionModel().currentChanged.connect(self._on_catalog_selected)

        # --- event table (right) ---
        self._event_model = EventTableModel()
        self._event_table = QTableView()
        self._event_table.setModel(self._event_model)
        self._event_table.selectionModel().currentChanged.connect(self._on_event_selected)

        # --- splitter ---
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._catalog_tree)
        self._splitter.addWidget(self._event_table)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)

        # --- toolbar ---
        self._add_event_btn = QPushButton("Add Event")
        self._add_event_btn.setVisible(False)
        self._add_event_btn.clicked.connect(self._on_add_event)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(self._on_delete)

        self._actions_btn = QToolButton()
        self._actions_btn.setText("Actions")
        self._actions_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._actions_menu = QMenu(self._actions_btn)
        self._actions_btn.setMenu(self._actions_menu)
        self._actions_btn.setVisible(False)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._add_event_btn)
        toolbar.addWidget(self._delete_btn)
        toolbar.addStretch()
        toolbar.addWidget(self._actions_btn)

        # --- layout ---
        layout = QVBoxLayout(self)
        layout.addWidget(self._filter_bar)
        layout.addWidget(self._splitter, 1)
        layout.addLayout(toolbar)

    # ---- slots ----

    def _on_catalog_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        node = self._tree_model.node_from_index(current)
        if node.catalog is not None:
            self._current_provider = node.provider
            self._current_catalog = node.catalog
            events = node.provider.events(node.catalog)
            self._event_model.set_events(events)
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

    def _on_add_event(self) -> None:
        pass  # To be implemented by higher-level code

    def _on_delete(self) -> None:
        pass  # To be implemented by higher-level code

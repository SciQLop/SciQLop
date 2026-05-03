from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLineEdit, QListView, QPushButton,
)


@dataclass
class ColumnEntry:
    key: str
    label: str
    visible: bool
    frozen: bool = False


class ColumnVisibilityPopover(QFrame):
    """Popover with search + checkable list + Show all / Hide all / Reset.

    Frozen columns are listed but cannot be hidden via this widget.
    """

    visibility_changed = Signal(str, bool)
    reorder_requested = Signal(list)  # new key order
    reset_requested = Signal()

    def __init__(self, entries: list[ColumnEntry], parent=None):
        super().__init__(parent)
        self.setObjectName("ColumnVisibilityPopover")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setWindowFlags(Qt.WindowType.Popup)

        self._entries: list[ColumnEntry] = list(entries)
        self._last_visible: dict[str, bool] = {e.key: e.visible for e in entries}

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Filter columns...")
        self._search.textChanged.connect(self.set_filter)

        self._model = QStandardItemModel(self)
        self._view = QListView(self)
        self._view.setModel(self._model)
        self._view.setDragDropMode(QListView.DragDropMode.InternalMove)
        self._view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._view.setMovement(QListView.Movement.Snap)
        self._model.itemChanged.connect(self._on_item_changed)
        self._model.rowsMoved.connect(lambda *_: self._emit_order())

        self._show_all_btn = QPushButton("Show all", self)
        self._hide_all_btn = QPushButton("Hide all", self)
        self._reset_btn = QPushButton("Reset", self)
        self._show_all_btn.clicked.connect(self.show_all)
        self._hide_all_btn.clicked.connect(self.hide_all)
        self._reset_btn.clicked.connect(self.reset_requested.emit)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._show_all_btn)
        btn_row.addWidget(self._hide_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._reset_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self._search)
        layout.addWidget(self._view, 1)
        layout.addLayout(btn_row)

        self._populate()

    def _populate(self) -> None:
        self._model.clear()
        for entry in self._entries:
            item = QStandardItem(entry.label)
            item.setCheckable(True)
            item.setCheckState(Qt.CheckState.Checked if entry.visible else Qt.CheckState.Unchecked)
            item.setData(entry.key, Qt.ItemDataRole.UserRole)
            if entry.frozen:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setToolTip("Frozen — cannot be hidden")
            self._model.appendRow(item)

    def set_filter(self, text: str) -> None:
        text_lower = text.lower()
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            self._view.setRowHidden(row, text_lower not in item.text().lower())

    def visible_entry_keys(self) -> list[str]:
        keys = []
        for row in range(self._model.rowCount()):
            if not self._view.isRowHidden(row):
                keys.append(self._model.item(row).data(Qt.ItemDataRole.UserRole))
        return keys

    def set_visible(self, key: str, visible: bool) -> None:
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                item.setCheckState(Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked)
                return

    def show_all(self) -> None:
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked)

    def hide_all(self) -> None:
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _on_item_changed(self, item: QStandardItem) -> None:
        key = item.data(Qt.ItemDataRole.UserRole)
        visible = item.checkState() == Qt.CheckState.Checked
        if self._last_visible.get(key) == visible:
            return
        self._last_visible[key] = visible
        self.visibility_changed.emit(key, visible)

    def _emit_order(self) -> None:
        order = [self._model.item(row).data(Qt.ItemDataRole.UserRole)
                 for row in range(self._model.rowCount())]
        self.reorder_requested.emit(order)

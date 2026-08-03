"""Grouped, filterable session-list panel with drag-drop and rename/pin/tag actions."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QMenu, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .sessions_view import PINNED_GROUP, UNGROUPED

_ID_ROLE = Qt.ItemDataRole.UserRole          # session id (session items)
_PIN_ROLE = Qt.ItemDataRole.UserRole + 1     # bool pinned (session items)
_GROUP_ROLE = Qt.ItemDataRole.UserRole + 2   # raw group name (header items; "" for ungrouped)
_KIND_ROLE = Qt.ItemDataRole.UserRole + 3    # "pinned" | "group" | "ungrouped" (header items)


def _resolve_drop_group(item):
    """Target group for a drop onto `item`: real group name, "" for ungrouped,
    or None to reject (the synthetic Pinned group)."""
    if item is None:
        return ""  # empty area -> ungrouped
    header = item if item.parent() is None else item.parent()
    kind = header.data(0, _KIND_ROLE)
    if kind == "pinned":
        return None
    if kind == "ungrouped":
        return ""
    return header.data(0, _GROUP_ROLE)


class _SessionTree(QTreeWidget):
    dropped = Signal(str, str)  # session_id, target_group ("" = ungrouped)

    def dropEvent(self, event):  # noqa: N802 (Qt override)
        source = self.currentItem()
        if source is None or source.parent() is None:
            event.ignore()
            return
        sid = source.data(0, _ID_ROLE)
        group = _resolve_drop_group(self.itemAt(event.position().toPoint()))
        if sid and group is not None:
            self.dropped.emit(sid, group)
        event.ignore()  # never let Qt move items — the tree is rebuilt from data


class SessionListPanel(QWidget):
    session_selected = Signal(str)
    rename_requested = Signal(str)
    pin_toggle_requested = Signal(str)
    move_requested = Signal(str)
    tags_edit_requested = Signal(str)
    session_delete_requested = Signal(str)
    session_moved = Signal(str, str)
    group_rename_requested = Signal(str)
    group_delete_requested = Signal(str)
    filter_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed: set[str] = set()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Sessions"))
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("filter name or tag…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self.filter_changed)
        layout.addWidget(self._filter)
        self._tree = _SessionTree()
        self._tree.setHeaderHidden(True)
        self._tree.setDragDropMode(QTreeWidget.DragDropMode.DragDrop)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.itemActivated.connect(lambda it, _c=0: self._on_activated(it))
        self._tree.itemClicked.connect(lambda it, _c=0: self._on_activated(it))
        self._tree.customContextMenuRequested.connect(self._on_menu)
        self._tree.itemCollapsed.connect(self._on_collapsed)
        self._tree.itemExpanded.connect(self._on_expanded)
        self._tree.dropped.connect(self.session_moved)
        layout.addWidget(self._tree, 1)

    def set_groups(self, groups, current_id=None) -> None:
        self._tree.blockSignals(True)
        self._tree.clear()
        for g in groups:
            kind = ("pinned" if g.name == PINNED_GROUP
                    else "ungrouped" if g.name == UNGROUPED else "group")
            header = QTreeWidgetItem(self._tree, [f"{g.name} ({len(g.sessions)})"])
            header.setData(0, _KIND_ROLE, kind)
            header.setData(0, _GROUP_ROLE, g.name)
            header.setFlags((header.flags() & ~Qt.ItemFlag.ItemIsDragEnabled
                             & ~Qt.ItemFlag.ItemIsSelectable) | Qt.ItemFlag.ItemIsDropEnabled)
            for s in g.sessions:
                child = QTreeWidgetItem(header, [("📌 " if s.pinned else "") + s.name])
                child.setData(0, _ID_ROLE, s.id)
                child.setData(0, _PIN_ROLE, bool(s.pinned))
                child.setFlags((child.flags() | Qt.ItemFlag.ItemIsDragEnabled)
                               & ~Qt.ItemFlag.ItemIsDropEnabled)
                if current_id is not None and s.id == current_id:
                    child.setSelected(True)
            header.setExpanded(g.name not in self._collapsed)
        self._tree.blockSignals(False)

    def _on_activated(self, item) -> None:
        if item is not None and item.parent() is not None:
            sid = item.data(0, _ID_ROLE)
            if sid:
                self.session_selected.emit(sid)

    def _on_collapsed(self, item) -> None:
        if item.parent() is None:
            self._collapsed.add(item.data(0, _GROUP_ROLE))

    def _on_expanded(self, item) -> None:
        if item.parent() is None:
            self._collapsed.discard(item.data(0, _GROUP_ROLE))

    def _emit_group_rename(self, header) -> None:
        self.group_rename_requested.emit(header.data(0, _GROUP_ROLE))

    def _emit_group_delete(self, header) -> None:
        self.group_delete_requested.emit(header.data(0, _GROUP_ROLE))

    def _group_menu(self, header) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Rename group…", lambda: self._emit_group_rename(header))
        menu.addAction("Delete group", lambda: self._emit_group_delete(header))
        return menu

    def session_menu(self, item) -> QMenu:
        sid = item.data(0, _ID_ROLE)
        pinned = bool(item.data(0, _PIN_ROLE))
        menu = QMenu(self)
        menu.addAction("Rename…", lambda: self.rename_requested.emit(sid))
        menu.addAction("Unpin" if pinned else "Pin",
                       lambda: self.pin_toggle_requested.emit(sid))
        menu.addAction("Move to group…", lambda: self.move_requested.emit(sid))
        menu.addAction("Edit tags…", lambda: self.tags_edit_requested.emit(sid))
        menu.addSeparator()
        menu.addAction("Delete session…", lambda: self.session_delete_requested.emit(sid))
        return menu

    def _on_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return
        if item.parent() is None and item.data(0, _KIND_ROLE) != "group":
            return  # no menu for Pinned / Ungrouped headers
        menu = self._group_menu(item) if item.parent() is None else self.session_menu(item)
        menu.exec(self._tree.mapToGlobal(pos))

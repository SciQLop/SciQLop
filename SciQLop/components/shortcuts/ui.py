from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QAbstractScrollArea, QDialog, QKeySequenceEdit, QLabel, QLineEdit, QStyle,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from SciQLop.components.settings.ui.settings_delegates import SettingDelegate, register_widget
from SciQLop.core.ui import Metrics
from SciQLop.core.ui.shortcuts import native_shortcut_text
from .registry import Shortcut, conflicts, key_for, on_shortcuts_changed, registered_shortcuts


def _grouped() -> dict[str, list[Shortcut]]:
    groups: dict[str, list[Shortcut]] = {}
    for shortcut in registered_shortcuts():
        groups.setdefault(shortcut.group, []).append(shortcut)
    return groups


def _portable(sequence: QKeySequence) -> str:
    return sequence.toString(QKeySequence.SequenceFormat.PortableText)


def _same_key(a: str, b: str) -> bool:
    return _portable(QKeySequence(a)) == _portable(QKeySequence(b))


def _tree(headers: list[str]) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setHeaderLabels(headers)
    tree.setRootIsDecorated(False)
    tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
    tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return tree


def _group_item(tree: QTreeWidget, group: str) -> QTreeWidgetItem:
    item = QTreeWidgetItem(tree, [group])
    font = item.font(0)
    font.setBold(True)
    item.setFont(0, font)
    item.setFirstColumnSpanned(True)
    item.setExpanded(True)
    return item


@register_widget("shortcuts")
class ShortcutsEditor(SettingDelegate):
    """Settings editor: one key-capture field per shortcut, a reset button,
    and a warning on rows that share a key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._tree = _tree(["Action", "Shortcut", ""])
        self._tree.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self._tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._tree)
        self._items: dict[str, QTreeWidgetItem] = {}
        self._edits: dict[str, QKeySequenceEdit] = {}
        self._resets: dict[str, QToolButton] = {}
        self._unlisted: dict[str, str] = {}
        for group, shortcuts in _grouped().items():
            group_item = _group_item(self._tree, group)
            for shortcut in shortcuts:
                self._add_row(group_item, shortcut)
        self._tree.resizeColumnToContents(0)

    def _add_row(self, group_item: QTreeWidgetItem, shortcut: Shortcut):
        item = QTreeWidgetItem(group_item, [shortcut.label])
        self._items[shortcut.id] = item
        if shortcut.fixed:
            item.setText(1, native_shortcut_text(shortcut.default))
            item.setToolTip(1, "This key can't be changed.")
            return
        edit = QKeySequenceEdit()
        edit.setMaximumSequenceLength(1)
        edit.setClearButtonEnabled(True)
        edit.keySequenceChanged.connect(self._on_edited)
        reset = QToolButton()
        reset.setText("Reset")
        reset.setToolTip(f"Restore the default key ({native_shortcut_text(shortcut.default)}).")
        reset.clicked.connect(lambda _=False, s=shortcut: edit.setKeySequence(QKeySequence(s.default)))
        self._tree.setItemWidget(item, 1, edit)
        self._tree.setItemWidget(item, 2, reset)
        self._edits[shortcut.id] = edit
        self._resets[shortcut.id] = reset

    def key_edit(self, shortcut_id: str) -> QKeySequenceEdit:
        return self._edits[shortcut_id]

    def reset_button(self, shortcut_id: str) -> QToolButton:
        return self._resets[shortcut_id]

    def conflict_text(self, shortcut_id: str) -> str:
        return self._items[shortcut_id].toolTip(0)

    def get_value(self) -> dict[str, str]:
        defaults = {s.id: s.default for s in registered_shortcuts()}
        keys = {sid: _portable(edit.keySequence()) for sid, edit in self._edits.items()}
        changed = {sid: key for sid, key in keys.items() if not _same_key(key, defaults[sid])}
        return {**self._unlisted, **changed}

    def set_value(self, value) -> None:
        overrides = value if isinstance(value, dict) else {}
        # Kept as-is: e.g. a disabled plugin's shortcut, not registered this session.
        self._unlisted = {sid: key for sid, key in overrides.items() if sid not in self._edits}
        for sid, edit in self._edits.items():
            edit.blockSignals(True)
            edit.setKeySequence(QKeySequence(key_for(sid, overrides)))
            edit.blockSignals(False)
        self._show_conflicts(overrides)

    def _on_edited(self, _sequence):
        value = self.get_value()
        self._show_conflicts(value)
        self.value_changed.emit(value)

    def _show_conflicts(self, overrides: dict[str, str]):
        labels = {s.id: s.label for s in registered_shortcuts()}
        found = conflicts(overrides)
        warning = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        for sid, item in self._items.items():
            others = found.get(sid, [])
            item.setToolTip(0, "Also used by: " + ", ".join(labels[o] for o in others) if others else "")
            item.setIcon(0, warning if others else QIcon())


class ShortcutsHelp(QDialog):
    """Read-only list of every shortcut, as currently bound."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setModal(False)
        layout = QVBoxLayout(self)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Search shortcuts…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter)
        self._tree = _tree(["Action", "Shortcut"])
        layout.addWidget(self._tree)
        hint = QLabel("Change them in Settings › Keyboard Shortcuts.")
        hint.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        layout.addWidget(hint)
        on_shortcuts_changed(self, lambda owner: owner._populate())
        self.resize(Metrics.size(35, 30))

    def _populate(self):
        self._tree.clear()
        for group, shortcuts in _grouped().items():
            group_item = _group_item(self._tree, group)
            for shortcut in shortcuts:
                QTreeWidgetItem(group_item, [shortcut.label, native_shortcut_text(key_for(shortcut.id))])
        self._tree.resizeColumnToContents(0)
        self._apply_filter(self.filter.text())

    def _apply_filter(self, text: str):
        needle = text.casefold()
        for g in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(g)
            group_matches = needle in group_item.text(0).casefold()
            shown = 0
            for c in range(group_item.childCount()):
                item = group_item.child(c)
                visible = group_matches or any(needle in item.text(col).casefold() for col in (0, 1))
                item.setHidden(not visible)
                shown += visible
            group_item.setHidden(shown == 0)

    def rows(self, visible_only: bool = False) -> list[tuple[str, str]]:
        return [(item.text(0), item.text(1))
                for g in range(self._tree.topLevelItemCount())
                for item in (self._tree.topLevelItem(g).child(c)
                             for c in range(self._tree.topLevelItem(g).childCount()))
                if not (visible_only and item.isHidden())]

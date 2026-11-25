"""The "History…" window: a project's or a catalogue's saved versions, grouped by day, with
Restore, Name and Copy as a new project."""
from __future__ import annotations

import asyncio
from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QMenu, QMessageBox,
    QPushButton, QStackedWidget, QStyle, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from .history import ProjectHistory, Version, when_text
from .icons import colour_dot
from .sharing_dialog import _settle, describe

COLUMNS = ["Time", "Who", "Name", "Changes"]
TIME, WHO, NAME, CHANGES = range(len(COLUMNS))
VERSION_ROLE = Qt.ItemDataRole.UserRole


def ask_text(parent, title: str, label: str, text: str = "") -> str | None:
    value, ok = QInputDialog.getText(parent, title, label, text=text)
    return value.strip() if ok else None


def confirm(parent, title: str, question: str, action: str) -> bool:
    box = QMessageBox(QMessageBox.Icon.Question, title, question, QMessageBox.StandardButton.Cancel, parent)
    accept = box.addButton(action, QMessageBox.ButtonRole.AcceptRole)
    box.exec()
    return box.clickedButton() is accept


def day_label(day: date | None, today: date) -> str:
    if day is None:
        return "Not closed yet"
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    return f"{day:%A %d %B}" if day.year == today.year else f"{day:%A %d %B %Y}"


def _font(italic: bool = False, bold: bool = False) -> QFont:
    font = QApplication.font()
    font.setItalic(italic)
    font.setBold(bold)
    return font


def _muted():
    return QApplication.palette().color(QPalette.ColorRole.PlaceholderText)


def _version_item(version: Version) -> QTreeWidgetItem:
    item = QTreeWidgetItem([version.when.strftime("%H:%M") if version.when else "", version.who,
                            version.name, version.changes])
    item.setData(TIME, VERSION_ROLE, version)
    if version.colour:
        item.setIcon(WHO, colour_dot(version.colour))
    if version.named:
        item.setFont(NAME, _font(bold=True))
    else:
        item.setFont(NAME, _font(italic=True))
        item.setForeground(NAME, _muted())
    if version.restore:
        item.setFont(CHANGES, _font(italic=True))
    tip = f"Version {version.id}, {when_text(version.when) or 'not closed yet'}, by {version.who or 'unknown'}"
    for column in range(len(COLUMNS)):
        item.setToolTip(column, tip)
    return item


def _day_item(label: str) -> QTreeWidgetItem:
    item = QTreeWidgetItem([label])
    item.setFirstColumnSpanned(True)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
    item.setFont(TIME, _font(bold=True))
    return item


class HistoryDialog(QDialog):
    def __init__(self, history: ProjectHistory, title: str, on_copied=None, parent=None, today=None):
        super().__init__(parent)
        self._history = history
        self._on_copied = on_copied
        self._today = today or date.today()
        self._scope = "this catalogue" if history.catalogue else "the project"
        self.setWindowTitle(f"History: {title}")
        self.resize(720, 460)

        heading = QLabel(f"<b>{title}</b>")
        heading.setStyleSheet("font-size: 15px")
        self._summary = QLabel()
        self._summary.setStyleSheet("color: palette(placeholder-text)")
        refresh = QToolButton()
        refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        refresh.setToolTip("Refresh")
        refresh.setAutoRaise(True)
        refresh.clicked.connect(self.refresh)
        top = QHBoxLayout()
        top.addWidget(heading)
        top.addWidget(self._summary)
        top.addStretch()
        top.addWidget(refresh)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(COLUMNS)
        self._tree.setRootIsDecorated(False)
        self._tree.setItemsExpandable(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setStyleSheet("QTreeView::item { padding: 3px 4px; }")
        self._tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        header = self._tree.header()
        header.setStretchLastSection(True)
        for column in (TIME, WHO, NAME):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.itemSelectionChanged.connect(self._update_buttons)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_menu)

        self._placeholder = QLabel()
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setStyleSheet("color: palette(placeholder-text)")
        self._pages = QStackedWidget()
        self._pages.addWidget(self._placeholder)
        self._pages.addWidget(self._tree)

        self._status = QLabel()
        self._status.setWordWrap(True)

        self._actions = {
            "restore": QPushButton("Restore…"),
            "name": QPushButton("Name…"),
            "copy": QPushButton("Copy as new project…"),
        }
        tips = {"restore": f"Make {self._scope} as it was at this version; later changes stay in the history",
                "name": "Give this version a name, or take its name away",
                "copy": "A new project of yours holding this version"}
        for key, button in self._actions.items():
            button.setToolTip(tips[key])
            button.clicked.connect(getattr(self, f"_{key}_selected"))
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        bottom = QHBoxLayout()
        for button in self._actions.values():
            bottom.addWidget(button)
        bottom.addStretch()
        bottom.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._pages, 1)
        layout.addWidget(self._status)
        layout.addLayout(bottom)
        self._show_placeholder("Loading…")
        self._update_buttons()

    # ---- running server calls ----

    def _run(self, coroutine, then=None, failure: str = "Failed") -> None:
        task = asyncio.ensure_future(_settle(coroutine))
        task.add_done_callback(lambda done: self._finish(done.result(), then, failure))

    def _finish(self, result, then, failure: str) -> None:
        if isinstance(result, Exception):
            self._say(f"{failure}: {describe(result)}", error=True)
            if self._pages.currentWidget() is self._placeholder:
                self._show_placeholder("The history could not be loaded.")
        elif then is not None:
            then(result)

    def _say(self, text: str, error: bool = False) -> None:
        self._status.setStyleSheet("color: #c0392b" if error else "")
        self._status.setText(text)

    def refresh(self) -> None:
        self._run(self._history.load(), self.show_versions, "Could not load the history")

    # ---- actions on a version ----

    def _selected(self) -> Version | None:
        items = self._tree.selectedItems()
        return items[0].data(TIME, VERSION_ROLE) if items else None

    def _update_buttons(self) -> None:
        chosen = self._selected() is not None
        for button in self._actions.values():
            button.setEnabled(chosen)

    def _show_menu(self, position) -> None:
        item = self._tree.itemAt(position)
        if item is None or item.data(TIME, VERSION_ROLE) is None:
            return
        menu = QMenu(self)
        for key, button in self._actions.items():
            menu.addAction(button.text(), getattr(self, f"_{key}_selected"))
        menu.exec(self._tree.viewport().mapToGlobal(position))

    def restore(self, version: Version) -> None:
        self._say("")
        self._run(self._history.restore(version.id),
                  lambda _: (self._say(f"Restored the version of {when_text(version.when)}."), self.refresh()),
                  "Could not restore")

    def name(self, version: Version, name: str) -> None:
        self._say("")
        self._run(self._history.name(version.id, name), lambda _: self.refresh(), "Could not name the version")

    def copy(self, version: Version, name: str) -> None:
        self._say("")
        self._run(self._history.copy(version.id, name), lambda project_id: self._copied(project_id, name),
                  "Could not copy the version")

    def _copied(self, project_id: str, name: str) -> None:
        self._say(f"Copied to the new project '{name}'.")
        if self._on_copied is not None:
            self._on_copied(project_id, name)

    def _restore_selected(self) -> None:
        version = self._selected()
        if version and confirm(self, "Restore", f"Make {self._scope} as it was on {when_text(version.when)}?\n\n"
                                                "Later changes stay in the history, so this can be undone.",
                               "Restore"):
            self.restore(version)

    def _name_selected(self) -> None:
        version = self._selected()
        name = ask_text(self, "Name version", "Name (leave empty to remove it):",
                        version.name if version.named else "") if version else None
        if name is not None:
            self.name(version, name)

    def _copy_selected(self) -> None:
        version = self._selected()
        name = ask_text(self, "Copy as new project", "New project name:") if version else None
        if name:
            self.copy(version, name)

    # ---- showing versions ----

    def _empty_text(self) -> str:
        if self._history.catalogue:
            return "No saved version changed this catalogue yet.\n\nRight-click the catalogue > Save version… to make one."
        return "No saved version yet.\n\nRight-click the project > Save version of the whole project… to make one."

    def _show_placeholder(self, text: str) -> None:
        self._placeholder.setText(text)
        self._pages.setCurrentWidget(self._placeholder)

    def show_versions(self, versions: list[Version]) -> None:
        self._tree.clear()
        self._summary.setText(f"{len(versions)} version{'' if len(versions) == 1 else 's'}, newest first"
                              if versions else "")
        if not versions:
            self._show_placeholder(self._empty_text())
            return
        group, label = None, None
        for version in versions:
            day = version.when.date() if version.when else None
            if group is None or day_label(day, self._today) != label:
                label = day_label(day, self._today)
                group = _day_item(label)
                self._tree.addTopLevelItem(group)
            group.addChild(_version_item(version))
        self._tree.expandAll()
        self._pages.setCurrentWidget(self._tree)
        self._update_buttons()

    # ---- reading what is shown ----

    def days(self) -> list[str]:
        return [self._tree.topLevelItem(i).text(TIME) for i in range(self._tree.topLevelItemCount())]

    def rows(self) -> list[tuple[str, ...]]:
        return [tuple(group.child(i).text(c) for c in range(len(COLUMNS)))
                for group in (self._tree.topLevelItem(g) for g in range(self._tree.topLevelItemCount()))
                for i in range(group.childCount())]

    def select(self, index: int) -> None:
        items = [group.child(i) for group in (self._tree.topLevelItem(g)
                                              for g in range(self._tree.topLevelItemCount()))
                 for i in range(group.childCount())]
        self._tree.setCurrentItem(items[index])

    def buttons_enabled(self) -> bool:
        return all(button.isEnabled() for button in self._actions.values())

    def placeholder_text(self) -> str | None:
        return self._placeholder.text() if self._pages.currentWidget() is self._placeholder else None

    def status_text(self) -> str:
        return self._status.text()


def show_history_dialog(session, project_id: str, title: str, catalogue: str | None = None,
                        on_copied=None, parent=None) -> HistoryDialog:
    dialog = HistoryDialog(ProjectHistory(session, project_id, catalogue), title, on_copied, parent)
    dialog.show()
    dialog.refresh()
    return dialog

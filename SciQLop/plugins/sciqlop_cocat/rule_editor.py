"""A smart catalogue's rule as JSON, for rules one search line cannot say (merge, shift, window...):
checked as it is typed by previewing it in the background (count and first events), saved only when
it reads. Non-modal, as the web app's "Edit rule as JSON…"."""
from __future__ import annotations

import json

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from SciQLop.components.catalogs import Catalog
from SciQLop.components.catalogs.ui.latest_only import LatestOnly

from . import smart_search

CHECK_MS = 300
FIRST_EVENTS = 50


def count_text(count: int) -> str:
    if count == 0:
        return "No event matches"
    return "1 event matches" if count == 1 else f"{count} events match"


def preview_table(parent) -> QTableWidget:
    table = QTableWidget(0, 3, parent)
    table.setHorizontalHeaderLabels(["Start", "Stop", "Tags"])
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    header.setStretchLastSection(True)
    for column in (0, 1):  # the times, whole
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
    return table


def fill_table(table: QTableWidget, rows) -> None:
    table.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, text in enumerate((f"{row.start:%Y-%m-%d %H:%M:%S}", f"{row.stop:%Y-%m-%d %H:%M:%S}",
                                  ", ".join(row.meta.get("tags", ())))):
            table.setItem(i, j, QTableWidgetItem(text))


class RuleEditor(QDialog):
    def __init__(self, provider, catalog: Catalog, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self._provider, self._catalog = provider, catalog
        self._project = provider._rooms[catalog.path[0]]
        self.setWindowTitle(f"Edit as JSON — {catalog.name}")
        search = provider.catalog_search(catalog)
        self.text = QPlainTextEdit(json.dumps(search.rule if search else {}, indent=2))
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.problem = QLabel("")
        self.problem.setWordWrap(True)
        self.problem.setStyleSheet("color: #d0453a")
        self.problem.hide()
        self.count = QLabel("")
        self.table = preview_table(self)
        self.save_button = QPushButton("Save rule")
        self.save_button.setEnabled(False)
        self._lay_out()
        self._preview = LatestOnly(self)
        self._preview.done.connect(self._show_preview)
        self._preview.failed.connect(self._show_failure)
        self._check_timer = QTimer(self)
        self._check_timer.setSingleShot(True)
        self._check_timer.setInterval(CHECK_MS)
        self._check_timer.timeout.connect(self._check)
        self.text.textChanged.connect(self._edited)
        self.save_button.clicked.connect(self.save)
        self.finished.connect(lambda _result: self._preview.stop())
        self._check_timer.start()

    def _lay_out(self) -> None:
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_button)
        layout = QVBoxLayout(self)
        for widget, stretch in ((QLabel("Rule (JSON)"), 0), (self.text, 2), (self.problem, 0), (self.count, 0),
                                (self.table, 1)):
            layout.addWidget(widget, stretch)
        layout.addLayout(buttons)

    def _say(self, message: str | None) -> None:
        self.problem.setText(message or "")
        self.problem.setVisible(bool(message))

    def _edited(self) -> None:
        self.save_button.setEnabled(False)
        self._check_timer.start()

    def _rule(self):
        try:
            rule = json.loads(self.text.toPlainText())
        except json.JSONDecodeError as error:
            self._say(f"Not JSON: {error.msg} (line {error.lineno}, column {error.colno})")
            return None
        if not isinstance(rule, dict):
            self._say("A rule is a JSON object: {…}")
            return None
        return rule

    def _check(self) -> None:
        rule = self._rule()
        if rule is None:
            self.count.setText("")
            return
        self._say(None)
        project = self._project
        self._preview.submit(lambda: smart_search.preview(project, rule, limit=FIRST_EVENTS))

    def _show_preview(self, found) -> None:
        self.count.setText(count_text(found.count))
        fill_table(self.table, found.rows)
        self.save_button.setEnabled(True)

    def _show_failure(self, message: str) -> None:
        self.count.setText("")
        self.table.setRowCount(0)
        self._say(smart_search._sentence(message))

    def save(self) -> None:
        rule = self._rule()
        if rule is None:
            return
        try:
            self._provider.set_catalog_search(self._catalog, rule=rule)
        except Exception as error:
            return self._say(smart_search._sentence(str(error)))
        self.accept()

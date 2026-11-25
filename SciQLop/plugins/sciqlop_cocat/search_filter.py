"""The CoCat search box above a cocat-rs catalogue's events, as the web app has it: the search
language and plain words as a live filter, errors in plain words, presets, "Save as smart
catalogue…". A smart catalogue's box opens on "Its search": editing it previews what the catalogue
would hold, then Save changes or Revert; "Filter" narrows what it holds now without changing it."""
from __future__ import annotations

import cocat_rs
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
    QRadioButton, QToolButton, QVBoxLayout, QWidget,
)

from SciQLop.components.catalogs import CatalogEvent
from SciQLop.components.catalogs.ui.event_filter import BackgroundEventFilter
from SciQLop.components.catalogs.ui.latest_only import LatestOnly

from . import smart_search
from .search_line import SearchLine

PLACEHOLDER = "Filter or search: tag:shock confidence:>=0.7"
PREVIEW_LIMIT = 1000
SEARCH, FILTER = "search", "filter"
SAVABLE = ("words", "rule")


def would_match(count: int) -> str:
    if count == 0:
        return "No event would match"
    return "1 event would match" if count == 1 else f"{count:,} events would match"


def ask_smart_catalogue(parent, name: str, can_look_in: bool) -> tuple[str, bool] | None:
    """A name, and whether to look in the shown catalogue (else in all events of the project)."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Save as smart catalogue")
    form = QFormLayout(dialog)
    name_box = QLineEdit(name)
    form.addRow("Name:", name_box)
    here, everywhere = QRadioButton("this catalogue"), QRadioButton("all events of the project")
    here.setChecked(can_look_in)
    everywhere.setChecked(not can_look_in)
    here.setEnabled(can_look_in)
    look_in = QVBoxLayout()
    look_in.addWidget(here)
    look_in.addWidget(everywhere)
    form.addRow("Look in:", look_in)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    buttons.addButton("Create", QDialogButtonBox.ButtonRole.AcceptRole)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted or not name_box.text().strip():
        return None
    return name_box.text().strip(), here.isChecked()


def _preview_events(rows) -> list[CatalogEvent]:
    return [CatalogEvent(uuid=row.uuid, start=row.start, stop=row.stop, meta=row.meta) for row in rows]


class CocatSearchFilter(BackgroundEventFilter):
    def __init__(self, provider, catalog, parent=None):
        super().__init__(parent)
        self._provider, self._catalog = provider, catalog
        self._room = provider._room_of(catalog)
        self._search = provider.catalog_search(catalog)  # a smart catalogue's own
        self._editable = provider._can_edit_search(catalog)
        self._filter_text = ""
        self._mode = FILTER
        self._previewing = False
        self._worker.failed.disconnect()
        self._worker.failed.connect(self._say)
        self._previewer = LatestOnly(self)
        self._previewer.done.connect(self._show_preview)
        self._previewer.failed.connect(self._say)
        self._widget = self._build()
        self._words = LatestOnly(self)
        self._words.done.connect(self.line.set_vocabulary)
        self._words.submit(self._room.vocabulary)
        self._enter(SEARCH if self._search is not None else FILTER)

    # ---- the widget ----

    def _build(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._box_row())
        self.problem = QLabel("")
        self.problem.setWordWrap(True)
        self.problem.hide()
        layout.addWidget(self.problem)
        layout.addLayout(self._preview_row())
        return widget

    def _box_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._modes = self._mode_buttons()
        for button in self._modes.buttons():
            row.addWidget(button)
        self.line = SearchLine()
        self.line.setPlaceholderText(PLACEHOLDER)
        self.line.textChanged.connect(self._on_text_edited)
        self.no_text = QLabel("This search has no text form.")
        self.edit_json = QPushButton("Edit as JSON…")
        self.edit_json.clicked.connect(lambda: self._provider.open_rule_editor(self._catalog))
        self.presets = self._presets_button()
        self.save_as = QPushButton("Save as smart catalogue…")
        self.save_as.clicked.connect(self._save_as)
        for part in (self.line, self.no_text, self.edit_json, self.presets, self.save_as):
            row.addWidget(part)
        row.setStretchFactor(self.line, 1)
        return row

    def _mode_buttons(self) -> QButtonGroup:
        group = QButtonGroup(self)
        for mode, text, tip in ((SEARCH, "Its search", "Edit what this smart catalogue holds"),
                                (FILTER, "Filter", "Narrow what it holds now, without changing it")):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.setCheckable(True)
            if self._search is None:
                button.hide()  # never show() it here: without a parent yet, it would open as a window of its own
            button.clicked.connect(lambda _checked, m=mode: self._enter(m))
            group.addButton(button)
            button.setProperty("mode", mode)
        return group

    def _presets_button(self) -> QToolButton:
        button = QToolButton()
        button.setText("Presets")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        for preset in cocat_rs.presets(self._provider._author):
            menu.addAction(preset["name"]).triggered.connect(lambda _c=False, q=preset["query"]: self.line.setPlainText(q))
        button.setMenu(menu)
        return button

    def _preview_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.count = QLabel("")
        self.save = QPushButton("Save changes")
        self.save.clicked.connect(self._save)
        self.revert = QPushButton("Revert")
        self.revert.clicked.connect(self._revert)
        row.addWidget(self.count, 1)
        row.addWidget(self.save)
        row.addWidget(self.revert)
        self._show_preview_row(False)
        return row

    # ---- EventFilter ----

    def widget(self) -> QWidget:
        return self._widget

    def query(self) -> str:
        return self.line.toPlainText()

    def prepare(self, events: list):
        return smart_search.match_items(events), [e.uuid for e in events]

    def state(self):
        if self._filter_text or self._mode != self._first_mode():
            return {"mode": self._mode, "filter": self._filter_text}
        return None

    def restore(self, state) -> None:
        self._filter_text = state["filter"]
        self._enter(state["mode"])

    def clear(self) -> None:
        self._filter_text = ""
        self._enter(self._mode)

    def focus(self) -> None:
        if self._search is not None and self._mode != SEARCH:
            self._enter(SEARCH)
        self.line.setFocus()

    def dispose(self) -> None:
        super().dispose()
        self._previewer.stop()
        self._words.stop()

    # ---- the two modes ----

    def mode(self) -> str:
        return self._mode

    def show_search(self) -> None:
        self._enter(SEARCH)

    def show_filter(self) -> None:
        self._enter(FILTER)

    def _first_mode(self) -> str:
        return SEARCH if self._search is not None else FILTER

    def _enter(self, mode: str) -> None:
        self._mode = mode
        searching = mode == SEARCH
        next(b for b in self._modes.buttons() if b.property("mode") == mode).setChecked(True)
        text_form = not searching or self._search.query is not None
        self.line.setVisible(text_form)
        self.line.setReadOnly(searching and not self._editable)
        self.no_text.setVisible(not text_form)
        self.edit_json.setVisible(not text_form and self._editable)
        self.presets.setVisible(text_form and not self.line.isReadOnly())
        self.save_as.hide()
        self._show_problem(None)
        self._end_preview()
        if searching:
            BackgroundEventFilter._apply(self, None)  # its search filters nothing: it says what the catalogue holds
        self._set_text(self._saved_text() if searching else self._filter_text)
        self.refilter()

    def _set_text(self, text: str) -> None:
        self.line.blockSignals(True)
        self.line.setPlainText(text)
        self.line.blockSignals(False)
        self.line.moveCursor(self.line.textCursor().MoveOperation.End)

    def _on_text_edited(self) -> None:
        if self._mode == FILTER:
            self._filter_text = self.line.toPlainText()
        self.query_edited()

    def refilter(self) -> None:
        self._debounce.stop()
        text = self.line.toPlainText()
        if self._mode == SEARCH:
            return self._preview(text)
        if not text.strip() or self._events is None:
            self._show_problem(None)
            self.save_as.hide()
            return BackgroundEventFilter._apply(self, None)
        room, (items, ids) = self._room, self.prepared()
        self._worker.submit(lambda: smart_search.filter_answer(room, text, items, ids))

    def _apply(self, answer: smart_search.Answer) -> None:
        if self._mode != FILTER:
            return  # a filter's answer arriving after the switch to its search
        self._show_problem(answer.problem)
        self.save_as.setVisible(answer.kind in SAVABLE and self._provider._can_save_search_from(self._catalog))
        if answer.kind != "broken":  # else the table keeps the last good filter
            super()._apply(answer.kept)

    def _show_problem(self, found: smart_search.Problem | None) -> None:
        self.line.underline(found.start if found else None, found.length if found else 0)
        self._say(found.message if found else None)

    def _say(self, message: str | None) -> None:
        self.problem.setText(message or "")
        self.problem.setVisible(bool(message))

    # ---- its search: preview, Save changes, Revert ----

    def _source_uuid(self) -> str | None:
        if self._mode != SEARCH or self._search.source is None:
            return None
        return self._search.source.uuid

    def _preview(self, text: str) -> None:
        if text == self._saved_text():
            self._show_problem(None)
            return self._end_preview()
        self.revert.show()
        room, source = self._room, self._source_uuid()
        self._previewer.submit(lambda: smart_search.preview_answer(room, text, source, PREVIEW_LIMIT))

    def _saved_text(self) -> str:
        return self._search.query or ""

    def _show_preview(self, answer: smart_search.Answer) -> None:
        if self._mode != SEARCH or self.line.toPlainText() == self._saved_text():
            return  # an answer arriving after Revert, Save or the switch to Filter
        self._show_problem(answer.problem)
        if answer.preview is None:  # broken or empty: nothing to save, the last preview stays
            return self.save.hide()
        self._previewing = True
        self.count.setText(would_match(answer.preview.count))
        self._show_preview_row(True)
        self.save.setVisible(self._editable)
        self.shown_events.emit(_preview_events(answer.preview.rows))

    def _show_preview_row(self, shown: bool) -> None:
        for part in (self.count, self.save, self.revert):
            part.setVisible(shown)

    def _end_preview(self) -> None:
        self._show_preview_row(False)
        if self._previewing:
            self._previewing = False
            self.shown_events.emit(None)

    def _save(self) -> None:
        try:
            self._provider.set_catalog_search(self._catalog, self.line.toPlainText(), self._search.source)
        except Exception as error:
            return self._say(f"Cannot save the search: {error}")
        self._search = self._provider.catalog_search(self._catalog)
        self._end_preview()

    def _revert(self) -> None:
        self._debounce.stop()
        self._set_text(self._saved_text())
        self._show_problem(None)
        self._end_preview()

    # ---- Save as smart catalogue… ----

    def _save_as(self) -> None:
        text = self.line.toPlainText()
        can_look_in = not self._provider._is_all_events(self._catalog)
        answer = ask_smart_catalogue(self._widget, text, can_look_in)
        if answer is None:
            return
        name, in_catalogue = answer
        try:
            made = self._provider.create_smart_catalog(name, list(self._catalog.path), text,
                                                       self._catalog if can_look_in and in_catalogue else None)
        except Exception as error:
            return self._say(f"Cannot make the smart catalogue: {error}")
        self._provider.open_requested.emit(made)

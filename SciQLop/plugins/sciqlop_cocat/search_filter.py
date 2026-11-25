"""The CoCat search box above a cocat-rs catalogue's events, as the web app has it: the search
language and plain words, errors in plain words, presets, "Save as smart catalogue…", and "Search in"
under the box. "This catalogue" filters what it holds, nothing saved. "All events" (the whole
project) and "Public catalogues" (the server's) preview what the catalogue would hold with that
search as its own, then Save or Revert. A catalogue with a search opens on where it looks. A
project's "All events" has a "Public catalogues" switch instead, which only shows what they hold."""
from __future__ import annotations

import cocat_rs
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QPushButton, QRadioButton, QToolButton, QVBoxLayout, QWidget,
)

from SciQLop.components.catalogs import CatalogEvent
from SciQLop.components.catalogs.ui.event_filter import BackgroundEventFilter
from SciQLop.components.catalogs.ui.latest_only import LatestOnly

from . import smart_search
from .search_line import SearchLine

PLACEHOLDER = "Filter or search: tag:shock confidence:>=0.7"
PREVIEW_LIMIT = 1000
SIGN_IN = "Sign in to search the public catalogues."
SEARCH, FILTER = "search", "filter"
CATALOGUE, ALL, PUBLIC, SOURCE = "catalogue", "all", "public", "source"
SCOPES = (
    (CATALOGUE, "This catalogue", "Filter what this catalogue holds. Nothing is saved."),
    (ALL, "All events", "Search the whole project. Save makes it this catalogue's own search: it then holds "
                        "every event the search finds, besides the events picked into it."),
    (PUBLIC, "Public catalogues", "Search every public catalogue on the server. Save makes it this catalogue's "
                                  "own search."),
    (SOURCE, "", "Its search looks in this catalogue."),
)
SAVABLE = ("words", "rule")


def found(count: int) -> str:
    if count == 0:
        return "No event found"
    return "1 event found" if count == 1 else f"{count:,} events found"


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


class CocatSearchFilter(BackgroundEventFilter):
    def __init__(self, provider, catalog, parent=None):
        super().__init__(parent)
        self._provider, self._catalog = provider, catalog
        self._room = provider._room_of(catalog)
        self._search = provider.catalog_search(catalog)  # the catalogue's own, if any
        self._every = provider._is_all_events(catalog)
        self._editable = provider._can_hold_search(catalog)
        self._filter_text = ""
        self._scope = None
        self._kept_before = None     # what the table showed before a text that does not read
        self._preview_before = None  # the same, for a preview
        self._previewing = False
        self._worker.failed.disconnect()
        self._worker.failed.connect(self._say)
        self._previewer = LatestOnly(self)
        self._previewer.done.connect(self._show_preview)
        self._previewer.failed.connect(self._preview_failed)
        self._widget = self._build()
        self._words = LatestOnly(self)
        self._words.done.connect(self.line.set_vocabulary)
        self._words.submit(self._room.vocabulary)
        self._enter(self._first_scope())

    # ---- the widget ----

    def _build(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._box_row())
        layout.addLayout(self._search_in_row())
        self._show_choices()  # once placed: un-hiding a widget without a parent opens it as a window
        self.problem = QLabel("")
        self.problem.setWordWrap(True)
        self.problem.hide()
        layout.addWidget(self.problem)
        layout.addLayout(self._preview_row())
        return widget

    def _box_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
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

    def _search_in_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.search_in_label = QLabel("Search in:")
        row.addWidget(self.search_in_label)
        self._scopes = QButtonGroup(self)
        for scope, text, tip in SCOPES:
            button = QRadioButton(text if scope != SOURCE else self._source_text())
            button.setToolTip(tip)
            button.setProperty("scope", scope)
            button.clicked.connect(lambda _checked, s=scope: self.search_in(s))
            self._scopes.addButton(button)
            row.addWidget(button)
        self.public_switch = QCheckBox("Public catalogues")
        self.public_switch.setToolTip("Search every public catalogue on the server instead of this project")
        self.public_switch.clicked.connect(lambda on: self.search_in(PUBLIC if on else CATALOGUE))
        row.addWidget(self.public_switch)
        row.addStretch()
        return row

    def _source_text(self) -> str:
        source = self._search.source if self._search is not None else None
        return f"In “{source.name}”" if source is not None else ""

    def _show_choices(self) -> None:
        """A project's All events: the switch. A catalogue: where to search, when it has a search or
        can hold one; read-only, only where its search looks can be shown."""
        choosing = not self._every and (self._editable or self._search is not None)
        self.search_in_label.setHidden(not (choosing or self._every))
        self.public_switch.setHidden(not self._every)
        for button in self._scopes.buttons():
            scope = button.property("scope")
            button.setHidden(not choosing or (scope == SOURCE and self._saved_scope() != SOURCE))
            button.setEnabled(self._editable or scope in (CATALOGUE, self._saved_scope()))

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
        self.save = QPushButton("Save")
        self.save.setToolTip("Make it this catalogue's own search")
        self.save.clicked.connect(self._save)
        self.revert = QPushButton("Revert")
        self.revert.clicked.connect(self._revert)
        row.addWidget(self.count)
        row.addStretch()
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
        if self._filter_text or self._scope != self._first_scope():
            return {"scope": self._scope, "filter": self._filter_text}
        return None

    def restore(self, state) -> None:
        self._filter_text = state["filter"]
        self._enter(state["scope"])

    def clear(self) -> None:
        self._filter_text = ""
        self._enter(self._scope)

    def focus(self) -> None:
        if self._search is not None and self._scope != self._saved_scope():
            self._enter(self._saved_scope())
        self.line.setFocus()

    def start_search(self) -> None:
        """A catalogue just made with New > Smart catalogue…: its search over all events, typed here, then Save."""
        if self._editable:
            self._enter(ALL)
        self.line.setFocus()

    def dispose(self) -> None:
        super().dispose()
        self._previewer.stop()
        self._words.stop()

    # ---- where it searches ----

    def mode(self) -> str:
        return FILTER if self._scope == CATALOGUE else SEARCH

    def scope(self) -> str:
        return self._scope

    def show_search(self) -> None:
        self.search_in(self._saved_scope() or ALL)

    def show_filter(self) -> None:
        self.search_in(CATALOGUE)

    def search_in(self, scope: str) -> None:
        self._enter(scope)

    def _saved_scope(self) -> str | None:
        if self._search is None:
            return None
        return PUBLIC if self._search.public else SOURCE if self._search.source is not None else ALL

    def _first_scope(self) -> str:
        return self._saved_scope() or CATALOGUE

    def _enter(self, scope: str, text: str | None = None) -> None:
        leaving, self._scope = self._scope, scope
        searching = scope != CATALOGUE
        self._check(scope)
        text_form = not searching or scope != self._saved_scope() or self._search.query is not None
        self.line.setVisible(text_form)
        self.line.setReadOnly(searching and not self._editable and not self._every)
        self.no_text.setVisible(not text_form)
        self.edit_json.setVisible(not text_form and self._editable)
        self.presets.setVisible(text_form and not self.line.isReadOnly())
        self.save_as.hide()
        self._show_problem(None)
        self._end_preview()
        if searching:
            BackgroundEventFilter._apply(self, None)  # a search of its own says what the catalogue holds
        self._set_text(text if text is not None else self._text_entering(scope, leaving))
        self.refilter()

    def _text_entering(self, scope: str, leaving: str | None) -> str:
        """Filtering: the filter's text. Searching: its own search's text, coming from the filter;
        the filter's text when it has none (a filter becoming its search); else the text as it is."""
        if scope == CATALOGUE:
            return self._filter_text
        if leaving in (None, CATALOGUE):
            return self._saved_text() if self._search is not None else self._filter_text
        return self.line.toPlainText()

    def _check(self, scope: str) -> None:
        for button in self._scopes.buttons():
            if button.property("scope") == scope:
                button.setChecked(True)
        self.public_switch.setChecked(scope == PUBLIC)

    def _set_text(self, text: str) -> None:
        self.line.blockSignals(True)
        self.line.setPlainText(text)
        self.line.blockSignals(False)
        self.line.moveCursor(self.line.textCursor().MoveOperation.End)

    def _on_text_edited(self) -> None:
        if self._scope == CATALOGUE:
            self._filter_text = self.line.toPlainText()
        self.query_edited()

    # ---- This catalogue: the filter ----

    def refilter(self) -> None:
        self._debounce.stop()
        text = self.line.toPlainText()
        if self.mode() == SEARCH:
            return self._preview(text)
        if not text.strip() or self._events is None:
            self._show_problem(None)
            self.save_as.hide()
            self._kept_before = None
            return BackgroundEventFilter._apply(self, None)
        room, (items, ids) = self._room, self.prepared()
        self._worker.submit(lambda: smart_search.filter_answer(room, text, items, ids))

    def _apply(self, answer: smart_search.Answer) -> None:
        if self.mode() != FILTER:
            return  # a filter's answer arriving after the switch to a search
        self._show_problem(answer.problem)
        self.save_as.setVisible(answer.kind in SAVABLE and self._provider._can_save_search_from(self._catalog))
        super()._apply(self._kept_for(answer))

    def _kept_for(self, answer: smart_search.Answer) -> set[str] | None:
        """A text that does not read leaves the table as before it. Plain words do not count as
        "before": half a search reads as words first (B_jump on the way to B_jump:>1), keeping nothing."""
        if answer.kind == "broken":
            return self._kept_before
        if answer.kind != "words":
            self._kept_before = answer.kept
        return answer.kept

    def _show_problem(self, found: smart_search.Problem | None) -> None:
        self.line.underline(found.start if found else None, found.length if found else 0)
        self._say(found.message if found else None)

    def _say(self, message: str | None) -> None:
        self.problem.setText(message[:1].upper() + message[1:] if message else "")
        self.problem.setVisible(bool(message))

    # ---- All events, Public catalogues: a search of its own, previewed, then Save or Revert ----

    def _preview_failed(self, why: str) -> None:
        """cocat-rs's sign-in error ends with a hint for programmers (Project.use_server)."""
        self._say(SIGN_IN if why.lower().startswith("sign in to search the public catalogues") else why)

    def _differs(self, text: str) -> bool:
        return (text, self._scope) != (self._saved_text(), self._saved_scope())

    def _preview(self, text: str) -> None:
        if not self._differs(text):
            self._show_problem(None)
            return self._end_preview()
        self.revert.setVisible(not self._every)
        room, public = self._room, self._scope == PUBLIC
        source = self._search.source.uuid if self._scope == SOURCE else None
        self._previewer.submit(lambda: smart_search.preview_answer(room, text, source, PREVIEW_LIMIT, public))

    def _saved_text(self) -> str:
        return (self._search.query or "") if self._search is not None else ""

    def _show_preview(self, answer: smart_search.Answer) -> None:
        if self.mode() != SEARCH or not self._differs(self.line.toPlainText()):
            return  # an answer arriving after Revert, Save or the switch to the filter
        self._show_problem(answer.problem)
        if answer.kind == "broken":
            return self._show_preview_before()
        if answer.preview is None:  # empty: nothing to show or save
            return self._end_preview(keep_revert=True)
        if answer.kind != "words":
            self._preview_before = answer
        self._show_rows(answer.preview)

    def _show_preview_before(self) -> None:
        """As for the filter: a text that does not read shows the last search that did, or the catalogue."""
        before = self._preview_before
        if before is None:
            return self._end_preview(keep_revert=True)
        self._show_rows(before.preview)

    def _show_rows(self, preview: smart_search.Preview) -> None:
        self._previewing = True
        self.count.setText(found(preview.count) if self._every else would_match(preview.count))
        self._show_preview_row(True)
        self.save.setVisible(self._editable)
        self.revert.setVisible(not self._every)
        self.shown_events.emit(self._events_of(preview.rows))

    def _events_of(self, rows) -> list[CatalogEvent]:
        return [CatalogEvent(uuid=row.uuid, start=row.start, stop=row.stop, meta=self._provider._named_public(row.meta))
                for row in rows]

    def _show_preview_row(self, shown: bool) -> None:
        for part in (self.count, self.save, self.revert):
            part.setVisible(shown)

    def _end_preview(self, keep_revert: bool = False) -> None:
        self._show_preview_row(False)
        self.revert.setVisible(keep_revert and not self._every)
        if not keep_revert:
            self._preview_before = None
        if self._previewing:
            self._previewing = False
            self.shown_events.emit(None)

    def _save(self) -> None:
        source = self._search.source if self._scope == SOURCE else None
        try:
            self._provider.set_catalog_search(self._catalog, self.line.toPlainText(), source,
                                              public=self._scope == PUBLIC)
        except Exception as error:
            return self._say(f"Cannot save the search: {error}")
        self._search = self._provider.catalog_search(self._catalog)
        self._show_choices()
        self._end_preview()

    def _revert(self) -> None:
        self._debounce.stop()
        saved = self._saved_scope()
        self._enter(saved, self._saved_text()) if saved is not None else self._enter(CATALOGUE)

    # ---- Save as smart catalogue… ----

    def _save_as(self) -> None:
        text = self.line.toPlainText()
        can_look_in = not self._every
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

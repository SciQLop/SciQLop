"""The filter above a catalogue's events in the catalog browser. A provider may supply its own
(CatalogProvider.event_filter, internal for now: not a plugin API yet); PlainTextFilter serves the
others. The browser hosts the delegate's widget, shows only the events it keeps, and remembers its state
per catalogue for the session.

Threading: everything here lives on the GUI thread. kept() only reads a result computed
beforehand; matching, anything proportional to the number of events, runs in a LatestOnly worker on
plain data (never the events themselves: they are Qt objects of the GUI thread)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, NamedTuple

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QLineEdit, QWidget

from ..backend.event_text import event_text, text_keeps
from .latest_only import LatestOnly

DEBOUNCE_MS = 150


class EventFilter(QObject):
    """What the browser asks of a filter delegate."""
    changed = Signal()  # the kept events changed: the table filters again
    shown_events = Signal(object)  # show these instead of the catalogue's, read-only (a preview); None: back

    def widget(self) -> QWidget:
        raise NotImplementedError

    def set_events(self, events: list) -> None:
        """The catalogue's events, at first and after each change."""
        raise NotImplementedError

    def kept(self) -> set[str] | None:
        """The uuids kept; None when nothing is filtered out. Cheap, GUI thread: reads the last
        result, computes nothing."""
        raise NotImplementedError

    def state(self) -> Any:
        """What the browser remembers for this catalogue for the session; None: nothing typed."""
        return None

    def restore(self, state: Any) -> None:
        """Back to a remembered state."""

    def clear(self) -> None:
        """Empty, at once: nothing filtered out."""

    def focus(self) -> None:
        """Ready for typing: a provider asked to show its catalogue (a search to edit)."""
        self.widget().setFocus()

    def start_search(self) -> None:
        """Ready to type the search of a catalogue just made with "New > Smart catalogue…": a delegate
        that searches beyond the catalogue opens there; by default the box just takes the focus."""
        self.focus()

    def dispose(self) -> None:
        """Stop the work in flight; the browser then deletes the widget."""


class BackgroundEventFilter(EventFilter):
    """An EventFilter whose matching runs off the GUI thread: a subclass says what plain data the
    events give (prepare, GUI thread) and how a query keeps them (match, any thread, pure); typing is
    debounced and only the answer to the last query is applied. prepare waits for the first query:
    opening a catalogue with nothing typed costs nothing."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._events: list | None = None
        self._data = None
        self._kept: set[str] | None = None
        self._worker = LatestOnly(self)
        self._worker.done.connect(self._apply)
        self._worker.failed.connect(lambda _why: self._apply(None))
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self.refilter)

    # ---- for subclasses ----

    def query(self) -> str:
        raise NotImplementedError

    def prepare(self, events: list):
        raise NotImplementedError

    @staticmethod
    def match(data, query: str) -> set[str] | None:
        raise NotImplementedError

    # ---- EventFilter ----

    def set_events(self, events: list) -> None:
        self._events, self._data = events, None
        if self.query().strip():
            self.refilter()

    def prepared(self):
        """The events as prepare gives them, made when a query first needs them."""
        if self._data is None and self._events is not None:
            self._data = self.prepare(self._events)
        return self._data

    def kept(self) -> set[str] | None:
        return self._kept

    def dispose(self) -> None:
        self._debounce.stop()
        self._worker.stop()

    # ---- the work ----

    def query_edited(self) -> None:
        self._debounce.start()

    def refilter(self) -> None:
        self._debounce.stop()
        query, match = self.query(), self.match
        if not query.strip() or self._events is None:
            return self._apply(None)
        data = self.prepared()
        self._worker.submit(lambda: match(data, query))

    def _apply(self, kept: set[str] | None) -> None:
        self._kept = kept
        self.changed.emit()


class _Row(NamedTuple):
    """An event as plain data: what event_text reads, safe in the worker."""
    uuid: str
    start: datetime
    stop: datetime
    meta: dict


class _Texts:
    """Each row's text, made once by the first search that needs it, in the worker: formatting
    100,000 rows takes about a second."""

    def __init__(self, rows: list[_Row]):
        self._rows, self._texts = rows, None

    def get(self) -> list[tuple[str, str]]:
        if self._texts is None:  # two jobs at once may both make it: the same answer, no harm
            self._texts = [(row.uuid, event_text(row)) for row in self._rows]
        return self._texts


class PlainTextFilter(BackgroundEventFilter):
    """Today's filter: a case-insensitive piece of text, matched against every column as the table
    shows it."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.box = QLineEdit()
        self.box.setPlaceholderText("Filter events…")
        self.box.setClearButtonEnabled(True)
        self.box.setToolTip("Filter the event table; matches any column.")
        self.box.textChanged.connect(lambda _text: self.query_edited())

    def widget(self) -> QWidget:
        return self.box

    def query(self) -> str:
        return self.box.text()

    def prepare(self, events: list):
        return _Texts([_Row(e.uuid, e.start, e.stop, dict(e.meta)) for e in events])

    @staticmethod
    def match(data, query: str) -> set[str] | None:
        return text_keeps(data.get(), query)

    def state(self):
        return self.box.text() or None

    def restore(self, state) -> None:
        self.box.setText(state or "")
        self.refilter()

    def clear(self) -> None:
        self.box.blockSignals(True)
        self.box.clear()
        self.box.blockSignals(False)
        self.refilter()
